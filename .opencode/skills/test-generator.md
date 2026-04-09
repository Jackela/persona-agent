---
name: test-generator
description: Generate comprehensive unit and integration tests. Use when asked to 'write tests', 'add test coverage', 'test this function', or when implementing new features that need testing. Supports pytest, unittest, and jest.
allowed-tools: Read, Grep, Bash(pytest*, python*)
---

# Test Generator Skill

Generate comprehensive tests following best practices and project conventions.

## Test Philosophy

- **Test behavior, not implementation** - Tests should pass even if internals change
- **One concept per test** - Each test should verify one thing
- **Arrange-Act-Assert** - Clear structure in every test
- **Independent tests** - No test should depend on another
- **Readable failures** - Clear error messages when tests fail

## Process

1. **Understand the Code**
   - Read the function/class to test
   - Identify inputs, outputs, and side effects
   - Note dependencies that need mocking

2. **Identify Test Cases**
   - Happy path (normal operation)
   - Edge cases (empty input, max values, etc.)
   - Error cases (exceptions, invalid input)
   - Boundary conditions

3. **Write Tests**
   - Use descriptive test names
   - Add docstrings explaining what is tested
   - Include type hints
   - Mock external dependencies

4. **Verify Coverage**
   - Run tests to ensure they pass
   - Check coverage report
   - Add missing test cases

## Python Testing with pytest

### Basic Structure

```python
import pytest
from unittest.mock import Mock, patch
from my_module import MyClass


class TestMyClass:
    """Test suite for MyClass."""
    
    @pytest.fixture
    def instance(self):
        """Create a fresh instance for each test."""
        return MyClass()
    
    def test_method_happy_path(self, instance):
        """Test normal operation of method."""
        # Arrange
        input_data = "valid_input"
        expected = "expected_output"
        
        # Act
        result = instance.method(input_data)
        
        # Assert
        assert result == expected
    
    def test_method_invalid_input_raises_error(self, instance):
        """Test that invalid input raises appropriate error."""
        # Arrange
        invalid_input = None
        
        # Act & Assert
        with pytest.raises(ValueError, match="Input cannot be None"):
            instance.method(invalid_input)
```

### Async Testing

```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await my_async_function()
    assert result is not None
```

### Mocking

```python
@patch('module.submodule.ExternalService')
def test_with_mocked_service(self, mock_service):
    """Test with external service mocked."""
    # Arrange
    mock_instance = Mock()
    mock_instance.fetch_data.return_value = {"key": "value"}
    mock_service.return_value = mock_instance
    
    # Act
    result = my_function()
    
    # Assert
    mock_instance.fetch_data.assert_called_once()
    assert result == {"key": "value"}
```

### Fixtures

```python
@pytest.fixture(scope="function")
def temp_file(tmp_path):
    """Create a temporary file for testing."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("test content")
    return file_path

@pytest.fixture(scope="module")
def database():
    """Create test database (once per module)."""
    db = create_test_db()
    yield db
    db.cleanup()
```

## JavaScript/TypeScript Testing with Jest

```typescript
describe('UserService', () => {
  let service: UserService;
  
  beforeEach(() => {
    service = new UserService();
  });
  
  describe('getUser', () => {
    it('should return user when found', async () => {
      // Arrange
      const userId = '123';
      const mockUser = { id: userId, name: 'John' };
      jest.spyOn(api, 'fetchUser').mockResolvedValue(mockUser);
      
      // Act
      const result = await service.getUser(userId);
      
      // Assert
      expect(result).toEqual(mockUser);
      expect(api.fetchUser).toHaveBeenCalledWith(userId);
    });
    
    it('should throw error when user not found', async () => {
      // Arrange
      jest.spyOn(api, 'fetchUser').mockRejectedValue(new Error('Not found'));
      
      // Act & Assert
      await expect(service.getUser('999'))
        .rejects
        .toThrow('User not found');
    });
  });
});
```

## Test Categories

### Unit Tests
- Test individual functions/methods in isolation
- Mock all dependencies
- Fast execution (< 100ms per test)
- High coverage (> 80%)

### Integration Tests
- Test component interactions
- Use real dependencies where appropriate
- Test database interactions
- Test API endpoints

### E2E Tests
- Test complete user workflows
- Use browser automation (Playwright, Selenium)
- Test critical paths only
- Slower but comprehensive

## Coverage Requirements

- **Lines**: Minimum 80%
- **Branches**: Minimum 75%
- **Functions**: Minimum 90%
- **Critical paths**: 100%

## Common Patterns

### Parameterized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("input1", "output1"),
    ("input2", "output2"),
    ("input3", "output3"),
])
def test_with_multiple_inputs(input, expected):
    """Test function with various inputs."""
    assert my_function(input) == expected
```

### Testing Exceptions

```python
def test_raises_specific_exception():
    """Test that correct exception is raised."""
    with pytest.raises(ValueError) as exc_info:
        risky_operation()
    
    assert str(exc_info.value) == "Expected error message"
```

### Testing Side Effects

```python
def test_file_written_correctly(tmp_path):
    """Test that file is written with correct content."""
    output_file = tmp_path / "output.txt"
    
    write_data("test data", output_file)
    
    assert output_file.exists()
    assert output_file.read_text() == "test data"
```

## Best Practices

1. **Use Test Descriptors**
   - `test_` prefix for pytest
   - Descriptive names: `test_calculation_with_negative_numbers`
   - Not: `test1`, `test_func`

2. **Keep Tests Focused**
   - One assertion per test (ideally)
   - Max 10-15 lines per test
   - Clear arrange/act/assert sections

3. **Use Fixtures for Setup**
   - Avoid duplicated setup code
   - Use appropriate scope (function, class, module)

4. **Mock External Dependencies**
   - Don't call real APIs in tests
   - Use dependency injection for easy mocking

5. **Test Edge Cases**
   - Empty collections
   - Null/None values
   - Maximum values
   - Unicode/special characters

6. **Maintain Test Data**
   - Use factories (factory_boy, faker)
   - Avoid hardcoded magic values
   - Keep test data close to tests

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_specific.py

# Run specific test
pytest tests/test_specific.py::TestClass::test_method

# Run with verbose output
pytest -v

# Run failing tests only
pytest --lf

# Run in parallel
pytest -n auto
```
