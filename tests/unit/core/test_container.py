import asyncio
import contextlib
import threading

import pytest

from persona_agent.core.container import (
    Container,
    ContainerError,
    RegistrationNotFoundError,
)


class DummyService:
    def __init__(self, value: int = 42) -> None:
        self.value = value


class DependentService:
    def __init__(self, dep: DummyService) -> None:
        self.dep = dep


class ServiceWithDefaults:
    def __init__(self, dep: DummyService, extra: str = "default") -> None:
        self.dep = dep
        self.extra = extra


class ServiceNoHints:
    def __init__(self, dep=None):
        self.dep = dep


class CounterService:
    _counter = 0

    def __init__(self) -> None:
        CounterService._counter += 1
        self.id = CounterService._counter


class TestContainerBasics:
    def test_register_and_resolve_by_type(self):
        container = Container()
        container.register(DummyService, DummyService)
        svc = container.resolve(DummyService)
        assert isinstance(svc, DummyService)
        assert svc.value == 42

    def test_register_and_resolve_by_name(self):
        container = Container()
        container.register("my_service", DummyService)
        svc = container.resolve("my_service")
        assert isinstance(svc, DummyService)

    def test_register_instance(self):
        container = Container()
        instance = DummyService(value=99)
        container.register_instance(DummyService, instance)
        svc = container.resolve(DummyService)
        assert svc is instance
        assert svc.value == 99

    def test_resolve_not_found_raises(self):
        container = Container()
        with pytest.raises(RegistrationNotFoundError):
            container.resolve(DummyService)

    def test_resolve_not_found_by_name_raises(self):
        container = Container()
        with pytest.raises(RegistrationNotFoundError):
            container.resolve("missing")

    def test_singleton_returns_same_instance(self):
        container = Container()
        container.register(CounterService, CounterService, singleton=True)
        a = container.resolve(CounterService)
        b = container.resolve(CounterService)
        assert a is b
        assert a.id == 1

    def test_transient_returns_new_instance(self):
        CounterService._counter = 0
        container = Container()
        container.register(CounterService, CounterService, singleton=False)
        a = container.resolve(CounterService)
        b = container.resolve(CounterService)
        assert a is not b
        assert a.id == 1
        assert b.id == 2

    def test_register_instance_always_singleton(self):
        container = Container()
        container.register_instance("tool", DummyService())
        a = container.resolve("tool")
        b = container.resolve("tool")
        assert a is b


class TestContainerAsync:
    @pytest.mark.asyncio
    async def test_aresolve_sync_factory(self):
        container = Container()
        container.register(DummyService, DummyService)
        svc = await container.aresolve(DummyService)
        assert isinstance(svc, DummyService)

    @pytest.mark.asyncio
    async def test_aresolve_async_factory(self):
        async def async_factory():
            return DummyService(value=77)

        container = Container()
        container.register(DummyService, async_factory)
        svc = await container.aresolve(DummyService)
        assert svc.value == 77

    @pytest.mark.asyncio
    async def test_aresolve_singleton_same_instance(self):
        container = Container()
        container.register(CounterService, CounterService, singleton=True)
        a = await container.aresolve(CounterService)
        b = await container.aresolve(CounterService)
        assert a is b

    @pytest.mark.asyncio
    async def test_aresolve_transient_new_instance(self):
        container = Container()
        container.register(CounterService, CounterService, singleton=False)
        a = await container.aresolve(CounterService)
        b = await container.aresolve(CounterService)
        assert a is not b

    @pytest.mark.asyncio
    async def test_aresolve_not_found(self):
        container = Container()
        with pytest.raises(RegistrationNotFoundError):
            await container.aresolve(DummyService)

    @pytest.mark.asyncio
    async def test_aresolve_concurrent_singleton_creation(self):
        call_count = 0

        async def slow_factory():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.05)
            return DummyService(value=call_count)

        container = Container()
        container.register(DummyService, slow_factory, singleton=True)

        results = await asyncio.gather(
            container.aresolve(DummyService),
            container.aresolve(DummyService),
            container.aresolve(DummyService),
        )

        assert all(r is results[0] for r in results)
        assert call_count == 1


class TestContainerOverride:
    def test_override_replaces_registration(self):
        container = Container()
        original = DummyService(value=1)
        override = DummyService(value=2)
        container.register_instance(DummyService, original)

        with container.override(DummyService, override):
            svc = container.resolve(DummyService)
            assert svc is override
            assert svc.value == 2

    def test_override_restores_after_exit(self):
        container = Container()
        original = DummyService(value=1)
        override = DummyService(value=2)
        container.register_instance(DummyService, original)

        with container.override(DummyService, override):
            pass

        svc = container.resolve(DummyService)
        assert svc is original

    def test_override_on_unregistered_adds_then_removes(self):
        container = Container()
        override = DummyService(value=99)

        with container.override(DummyService, override):
            svc = container.resolve(DummyService)
            assert svc is override

        with pytest.raises(RegistrationNotFoundError):
            container.resolve(DummyService)

    def test_override_nested(self):
        container = Container()
        a = DummyService(value=1)
        b = DummyService(value=2)
        container.register_instance(DummyService, a)

        with container.override(DummyService, b):
            with container.override(DummyService, a):
                assert container.resolve(DummyService) is a
            assert container.resolve(DummyService) is b
        assert container.resolve(DummyService) is a


class TestContainerAutowire:
    def test_autowire_class_with_dependency(self):
        container = Container()
        container.register(DummyService, DummyService)
        svc = container.autowire(DependentService)
        assert isinstance(svc.dep, DummyService)

    def test_autowire_skips_defaults(self):
        container = Container()
        container.register(DummyService, DummyService)
        svc = container.autowire(ServiceWithDefaults)
        assert isinstance(svc.dep, DummyService)
        assert svc.extra == "default"

    def test_autowire_skips_no_hints(self):
        container = Container()
        container.register(DummyService, DummyService)
        svc = container.autowire(ServiceNoHints)
        assert svc.dep is None

    def test_autowire_resolve_invokes_autowire_for_class(self):
        container = Container()
        container.register(DummyService, DummyService)
        container.register(DependentService, DependentService)
        svc = container.resolve(DependentService)
        assert isinstance(svc.dep, DummyService)

    def test_autowire_aresolve_invokes_autowire_for_class(self):
        container = Container()
        container.register(DummyService, DummyService)
        container.register(DependentService, DependentService)

        async def run():
            return await container.aresolve(DependentService)

        svc = asyncio.run(run())
        assert isinstance(svc.dep, DummyService)

    def test_classmethod_autowire_raises(self):
        with pytest.raises(NotImplementedError):
            Container._autowire(DummyService)


class TestContainerThreadSafety:
    def test_thread_safe_singleton_creation(self):
        container = Container()
        call_count = 0
        lock = threading.Lock()

        def factory():
            nonlocal call_count
            with lock:
                call_count += 1
            return DummyService(value=call_count)

        container.register(DummyService, factory, singleton=True)

        results = []

        def worker():
            results.append(container.resolve(DummyService))

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(r is results[0] for r in results)

    def test_thread_safe_register_and_resolve(self):
        container = Container()
        errors = []
        resolved = []

        def register_worker(n):
            try:
                container.register(f"svc_{n}", DummyService)
            except Exception as e:
                errors.append(e)

        def resolve_worker(n):
            with contextlib.suppress(RuntimeError, KeyError):
                resolved.append(container.resolve(f"svc_{n}"))

        threads = []
        for i in range(20):
            threads.append(threading.Thread(target=register_worker, args=(i,)))
            threads.append(threading.Thread(target=resolve_worker, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(resolved) > 0


class TestContainerExceptions:
    def test_container_error_is_exception(self):
        assert issubclass(ContainerError, Exception)

    def test_registration_not_found_error_is_container_error(self):
        assert issubclass(RegistrationNotFoundError, ContainerError)
