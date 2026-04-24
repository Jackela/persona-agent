from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ContainerError(Exception):
    pass


class RegistrationNotFoundError(ContainerError):
    pass


class _Registration(Generic[T]):
    __slots__ = ("factory", "singleton", "instance", "lock")

    def __init__(
        self,
        factory: Callable[..., T] | type[T],
        *,
        singleton: bool = True,
    ) -> None:
        self.factory = factory
        self.singleton = singleton
        self.instance: T | None = None
        self.lock = asyncio.Lock()


class Container:
    def __init__(self) -> None:
        self._registry: dict[Any, _Registration[Any]] = {}
        self._registry_lock = threading.Lock()

    def register(
        self,
        interface: type[T] | str,
        factory: Callable[..., T] | type[T],
        *,
        singleton: bool = True,
    ) -> None:
        with self._registry_lock:
            self._registry[interface] = _Registration(factory, singleton=singleton)

    def register_instance(
        self,
        interface: type[T] | str,
        instance: T,
    ) -> None:
        reg: _Registration[T] = _Registration(lambda: instance, singleton=True)
        reg.instance = instance
        with self._registry_lock:
            self._registry[interface] = reg

    def resolve(self, interface: type[T] | str) -> T:
        with self._registry_lock:
            reg = self._registry.get(interface)

        if reg is None:
            raise RegistrationNotFoundError(f"No registration found for {interface!r}")

        if not reg.singleton:
            return self._invoke_factory(reg.factory)

        if reg.instance is not None:
            return reg.instance

        instance = self._invoke_factory(reg.factory)
        with self._registry_lock:
            if reg.instance is None:
                reg.instance = instance
            return reg.instance

    async def aresolve(self, interface: type[T] | str) -> T:
        with self._registry_lock:
            reg = self._registry.get(interface)

        if reg is None:
            raise RegistrationNotFoundError(f"No registration found for {interface!r}")

        if not reg.singleton:
            return await self._ainvoke_factory(reg.factory)

        if reg.instance is not None:
            return reg.instance

        async with reg.lock:
            if reg.instance is None:
                reg.instance = await self._ainvoke_factory(reg.factory)
            return reg.instance  # type: ignore[return-value]

    @contextmanager
    def override(
        self,
        interface: type[T] | str,
        instance: T,
    ):
        with self._registry_lock:
            old_reg = self._registry.get(interface)
            self._registry[interface] = _Registration(lambda: instance, singleton=True)
            self._registry[interface].instance = instance

        try:
            yield
        finally:
            with self._registry_lock:
                if old_reg is None:
                    self._registry.pop(interface, None)
                else:
                    self._registry[interface] = old_reg

    @classmethod
    def _autowire(cls, target_class: type[T]) -> T:
        raise NotImplementedError(
            "_autowire requires a container instance. Use container.autowire() instead."
        )

    def autowire(self, target_class: type[T]) -> T:
        sig = inspect.signature(target_class.__init__)  # type: ignore[misc]
        kwargs: dict[str, Any] = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.default is not inspect.Parameter.empty:
                continue
            if param.annotation is inspect.Parameter.empty:
                continue
            kwargs[name] = self.resolve(param.annotation)
        return target_class(**kwargs)

    def _invoke_factory(self, factory: Callable[..., T] | type[T]) -> T:
        if inspect.isclass(factory):
            return self.autowire(factory)
        result = factory()
        return result  # type: ignore[return-value]

    async def _ainvoke_factory(self, factory: Callable[..., T] | type[T]) -> T:
        if inspect.isclass(factory):
            return self.autowire(factory)
        if asyncio.iscoroutinefunction(factory):
            result = await factory()
            return result  # type: ignore[return-value]
        result = factory()
        return result  # type: ignore[return-value]
