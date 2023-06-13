# Rusty error handling

Rust like error handling in python.

Reference from rust document:
https://doc.rust-lang.org/book/ch09-00-error-handling.html

Use by Nguyen Hoang Khoi for his awesome youtube channel

# Usage

## Simple example

### Using Result[T, R] and unwrap

```python
from rusty import Result, Ok, Err
from enum import Enum


class Error(Enum):
    E_INVALID = 1
    E_PERMISSON_DENIED = 2


def test_func(input: Error | int) -> Result[int, Error]:
    if isinstance(input, Error):
        return Err[Error](input)
    return Ok[int](input)


# Use match to check the return result
result = test_func(Error.E_INVALID)
match result:
    case Err(content):
        print(f"ERROR: {content}")
    case Ok(content):
        print(f"OK: {content}")


# Or unwrap to get the data
from rusty import unwrap

result = test_func(10)
result = unwrap(result)
print(f"Result: {result}")

# unwrap Err will raise exception
from rusty import ResultError

result = test_func(Error.E_PERMISSON_DENIED)
try:
    result = unwrap(result)
    print(f"Result: {result}")
except ResultError as e:
    print(e)
```