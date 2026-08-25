 import string                                                                    +


 def generate_password(length=16, include_special=True, include_numbers=True):    +
     """Generate a cryptographically secure random password.                      +

     Args:                                                                        +
         length: Password length (1-128). Defaults to 16.                         +
         include_special: Whether to include special characters. Defaults to True.+
         include_numbers: Whether to include digits. Defaults to True.            +

     Returns:                                                                     +
         A randomly generated password string.                                    +

     Raises:                                                                      +
         ValueError: If length is not between 1 and 128.                          +
         TypeError: If any argument is of an invalid type.                        +
     """                                                                          +
     # Validate length type                                                       +
     if not isinstance(length, int) or isinstance(length, bool):                  +
         raise TypeError("Length must be an integer.")                            +

     # Validate length bounds                                                     +
     if length < 1 or length > 128:                                               +
         raise ValueError("Length must be an integer between 1 and 128.")         +

     # Validate include_special type                                              +
     if not isinstance(include_special, bool):                                    +
         raise TypeError("include_special must be a boolean.")                    +

     # Validate include_numbers type                                              +
     if not isinstance(include_numbers, bool):                                    +
         raise TypeError("include_numbers must be a boolean.")                    +

     # Base character set: uppercase + lowercase letters                          +
     characters = string.ascii_uppercase + string.ascii_lowercase                 +

     # Opt-in additions                                                           +
     if include_numbers:                                                          +
         characters += string.digits                                              +

     if include_special:                                                          +
         characters += string.punctuation                                         +

     return ''.join(secrets.choice(characters) for _ in range(length))

