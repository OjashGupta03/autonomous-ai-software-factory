
 A lightweight, cryptographically secure password generator for Python. Generates random passwords with configurable length and character sets using Python's `secrets` module.+

 ## Features                                                                                                                                                                   +

 - **Cryptographically secure** – Uses Python's `secrets` module (not `random`) for unpredictable password generation.                                                         +
 - **Configurable length** – Supports passwords from 1 to 128 characters.                                                                                                      +
 - **Customizable character sets** – Optionally include digits and special characters.                                                                                         +
 - **CLI interface** – Generate passwords directly from the command line.                                                                                                      +
 - **Python API** – Import and use programmatically in your own projects.                                                                                                      +

 ## Installation                                                                                                                                                               +

 No external dependencies are required. This project runs on **Python 3.6+** using only the standard library.                                                                  +

 ```bash                                                                                                                                                                       +
 # Clone the repository                                                                                                                                                        +
 git clone <repository-url>                                                                                                                                                    +
 cd password-generator                                                                                                                                                         +

 # That's it! No pip install needed.                                                                                                                                           +
 ```                                                                                                                                                                           +

 ## Usage                                                                                                                                                                      +

 ### Command-Line Interface                                                                                                                                                    +

 Generate a password of length 20 with special characters and numbers:                                                                                                         +

 ```bash                                                                                                                                                                       +
 python cli.py 20 --special --numbers                                                                                                                                          +
 ```                                                                                                                                                                           +

 Generate a password of length 12 with only letters:                                                                                                                           +

 ```bash                                                                                                                                                                       +
 python cli.py 12                                                                                                                                                              +
 ```                                                                                                                                                                           +

 #### CLI Arguments                                                                                                                                                            +

 | Argument    | Type    | Required | Default | Description                          |                                                                                         +
 |-------------|---------|----------|---------|--------------------------------------|                                                                                         +
 | `length`    | `int`   | Yes      | –       | Length of the generated password     |                                                                                         +
 | `--special` | `flag`  | No       | `False` | Include special characters           |                                                                                         +
 | `--numbers` | `flag`  | No       | `False` | Include digits                       |                                                                                         +

 ### Python API                                                                                                                                                                +

 ```python                                                                                                                                                                     +
 from generator import generate_password                                                                                                                                       +

 # Generate a default 16-character password with special chars and numbers                                                                                                     +
 password = generate_password()                                                                                                                                                +
 print(password)  # e.g. 'kR3#mP9@xL2$vN7q'                                                                                                                                    +

 # Generate a 24-character password without special characters                                                                                                                 +
 password = generate_password(length=24, include_special=False)                                                                                                                +
 print(password)  # e.g. 'aB3cD4eF5gH6iJ7kL8mN9oP0'                                                                                                                            +

 # Generate an 8-character password with only letters                                                                                                                          +
 password = generate_password(length=8, include_special=False, include_numbers=False)                                                                                          +
 print(password)  # e.g. 'aBcDeFgH'                                                                                                                                            +
 ```                                                                                                                                                                           +

 ## API Documentation                                                                                                                                                          +

 ### `generator` Module                                                                                                                                                        +

 #### `generate_password(length=16, include_special=True, include_numbers=True) -> str`                                                                                        +

 Generates a cryptographically secure random password.                                                                                                                         +

 **Parameters:**                                                                                                                                                               +

 | Parameter         | Type      | Default | Description                                      |                                                                                +
 |-------------------|-----------|---------|--------------------------------------------------|                                                                                +
 | `length`          | `int`     | `16`    | Password length. Must be between 1 and 128.      |                                                                                +
 | `include_special` | `bool`    | `True`  | Whether to include special characters (`string.punctuation`). |                                                                   +
 | `include_numbers` | `bool`    | `True`  | Whether to include digits (`string.digits`).      |                                                                               +

 **Returns:**                                                                                                                                                                  +

 - `str` – A randomly generated password string.                                                                                                                               +

 **Raises:**                                                                                                                                                                   +

 - `ValueError` – If `length` is not between 1 and 128.                                                                                                                        +
 - `TypeError` – If `length` is not an integer, or if `include_special`/`include_numbers` are not booleans.                                                                    +

 **Character Sets:**                                                                                                                                                           +

 | Set               | Characters Included                          |                                                                                                          +
 |-------------------|----------------------------------------------|                                                                                                          +
 | Always            | Uppercase (`A-Z`) + Lowercase (`a-z`)        |                                                                                                          +
 | `include_numbers` | Digits (`0-9`)                                |                                                                                                         +
 | `include_special` | Punctuation (`!"#$%&'()*+,-./:;<=>?@[\]^_`{|}~`) |                                                                                                      +

 **Examples:**                                                                                                                                                                 +

 ```python                                                                                                                                                                     +
 from generator import generate_password                                                                                                                                       +

 # Default usage                                                                                                                                                               +
 pw = generate_password()                                                                                                                                                      +
 # length=16, includes letters, digits, and special characters                                                                                                                 +

 # Short password, letters only                                                                                                                                                +
 pw = generate_password(length=8, include_special=False, include_numbers=False)                                                                                                +

 # Long password with all character types                                                                                                                                      +
 pw = generate_password(length=64, include_special=True, include_numbers=True)                                                                                                 +
 ```                                                                                                                                                                           +

 ## Testing                                                                                                                                                                    +

 Run the test suite with `pytest`:                                                                                                                                             +

 ```bash                                                                                                                                                                       +
 pip install pytest                                                                                                                                                            +
 pytest                                                                                                                                                                        +
 ```                                                                                                                                                                           +

 ## License                                                                                                                                                                    +

 This project is provided as-is. Feel free to use and modify as needed.

