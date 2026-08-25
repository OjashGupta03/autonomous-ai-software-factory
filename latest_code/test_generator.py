 import string                                                                                                                       +
 from generator import generate_password                                                                                             +


 # ---------------------------------------------------------------------------                                                       +
 # Valid password generation with various lengths                                                                                    +
 # ---------------------------------------------------------------------------                                                       +

 class TestValidPasswordGeneration:                                                                                                  +
     """Test that passwords are generated correctly for valid inputs."""                                                             +

     def test_default_parameters(self):                                                                                              +
         """Default call should produce a 16-character password."""                                                                  +
         password = generate_password()                                                                                              +
         assert len(password) == 16                                                                                                  +

     def test_short_length(self):                                                                                                    +
         """A length of 1 should produce a single-character password."""                                                             +
         password = generate_password(length=1)                                                                                      +
         assert len(password) == 1                                                                                                   +

     def test_medium_length(self):                                                                                                   +
         """A length of 32 should produce a 32-character password."""                                                                +
         password = generate_password(length=32)                                                                                     +
         assert len(password) == 32                                                                                                  +

     def test_max_length(self):                                                                                                      +
         """A length of 128 should produce a 128-character password."""                                                              +
         password = generate_password(length=128)                                                                                    +
         assert len(password) == 128                                                                                                 +

     def test_different_calls_produce_different_passwords(self):                                                                     +
         """Two calls with the same arguments should almost certainly differ."""                                                     +
         passwords = {generate_password(length=16) for _ in range(10)}                                                               +
         # With 94 possible characters and length 16, collision probability is                                                       +
         # astronomically low; 10 unique passwords is a safe sanity check.                                                           +
         assert len(passwords) == 10                                                                                                 +


 # ---------------------------------------------------------------------------                                                       +
 # Inclusion / exclusion of special characters and numbers                                                                           +
 # ---------------------------------------------------------------------------                                                       +

 class TestCharacterInclusion:                                                                                                       +
     """Test that character sets are correctly included or excluded."""                                                              +

     def test_include_special_true(self):                                                                                            +
         """When include_special=True, at least one special char should appear."""                                                   +
         # Generate a reasonably long password so the probability of missing                                                         +
         # a special character is very low.                                                                                          +
         password = generate_password(length=64, include_special=True, include_numbers=True)                                         +
         assert any(c in string.punctuation for c in password)                                                                       +

     def test_include_special_false(self):                                                                                           +
         """When include_special=False, no special characters should appear."""                                                      +
         password = generate_password(length=64, include_special=False, include_numbers=True)                                        +
         assert not any(c in string.punctuation for c in password)                                                                   +

     def test_include_numbers_true(self):                                                                                            +
         """When include_numbers=True, at least one digit should appear."""                                                          +
         password = generate_password(length=64, include_special=True, include_numbers=True)                                         +
         assert any(c in string.digits for c in password)                                                                            +

     def test_include_numbers_false(self):                                                                                           +
         """When include_numbers=False, no digits should appear."""                                                                  +
         password = generate_password(length=64, include_special=True, include_numbers=False)                                        +
         assert not any(c in string.digits for c in password)                                                                        +

     def test_no_special_no_numbers(self):                                                                                           +
         """With both flags False, only letters should appear."""                                                                    +
         password = generate_password(length=32, include_special=False, include_numbers=False)                                       +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase)                                                              +
         assert all(c in allowed for c in password)                                                                                  +

     def test_only_special_no_numbers(self):                                                                                         +
         """With special=True and numbers=False, no digits but specials allowed."""                                                  +
         password = generate_password(length=64, include_special=True, include_numbers=False)                                        +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.punctuation)                                         +
         assert all(c in allowed for c in password)                                                                                  +
         assert not any(c in string.digits for c in password)                                                                        +

     def test_only_numbers_no_special(self):                                                                                         +
         """With special=False and numbers=True, no specials but digits allowed."""                                                  +
         password = generate_password(length=64, include_special=False, include_numbers=True)                                        +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.digits)                                              +
         assert all(c in allowed for c in password)                                                                                  +
         assert not any(c in string.punctuation for c in password)                                                                   +


 # ---------------------------------------------------------------------------                                                       +
 # Verification that passwords only contain allowed characters                                                                       +
 # ---------------------------------------------------------------------------                                                       +

 class TestAllowedCharacters:                                                                                                        +
     """Ensure generated passwords never contain disallowed characters."""                                                           +

     def test_all_allowed_with_all_options(self):                                                                                    +
         """Full character set: letters + digits + punctuation."""                                                                   +
         password = generate_password(length=64, include_special=True, include_numbers=True)                                         +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.digits + string.punctuation)                         +
         assert all(c in allowed for c in password)                                                                                  +

     def test_all_allowed_letters_only(self):                                                                                        +
         """Letters-only mode."""                                                                                                    +
         password = generate_password(length=64, include_special=False, include_numbers=False)                                       +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase)                                                              +
         assert all(c in allowed for c in password)                                                                                  +

     def test_all_allowed_letters_and_digits(self):                                                                                  +
         """Letters + digits mode."""                                                                                                +
         password = generate_password(length=64, include_special=False, include_numbers=True)                                        +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.digits)                                              +
         assert all(c in allowed for c in password)                                                                                  +

     def test_all_allowed_letters_and_special(self):                                                                                 +
         """Letters + special mode."""                                                                                               +
         password = generate_password(length=64, include_special=True, include_numbers=False)                                        +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.punctuation)                                         +
         assert all(c in allowed for c in password)                                                                                  +

     def test_no_whitespace(self):                                                                                                   +
         """Passwords should never contain whitespace."""                                                                            +
         password = generate_password(length=64, include_special=True, include_numbers=True)                                         +
         assert not any(c.isspace() for c in password)                                                                               +

     def test_no_control_characters(self):                                                                                           +
         """Passwords should never contain control characters."""                                                                    +
         password = generate_password(length=64, include_special=True, include_numbers=True)                                         +
         assert not any(c in string.ascii_letters + string.digits + string.punctuation for c in password if c.isprintable() is False)+


 # ---------------------------------------------------------------------------                                                       +
 # Input validation – out-of-bounds lengths                                                                                          +
 # ---------------------------------------------------------------------------                                                       +

 class TestLengthValidation:                                                                                                         +
     """Test that invalid length values raise appropriate exceptions."""                                                             +

     def test_length_zero_raises_value_error(self):                                                                                  +
         with pytest.raises(ValueError, match="Length must be an integer between 1 and 128"):                                        +
             generate_password(length=0)                                                                                             +

     def test_length_negative_raises_value_error(self):                                                                              +
         with pytest.raises(ValueError, match="Length must be an integer between 1 and 128"):                                        +
             generate_password(length=-1)                                                                                            +

     def test_length_129_raises_value_error(self):                                                                                   +
         with pytest.raises(ValueError, match="Length must be an integer between 1 and 128"):                                        +
             generate_password(length=129)                                                                                           +

     def test_length_large_raises_value_error(self):                                                                                 +
         with pytest.raises(ValueError, match="Length must be an integer between 1 and 128"):                                        +
             generate_password(length=1000)                                                                                          +

     def test_length_float_raises_type_error(self):                                                                                  +
         with pytest.raises(TypeError, match="Length must be an integer"):                                                           +
             generate_password(length=16.5)                                                                                          +

     def test_length_string_raises_type_error(self):                                                                                 +
         with pytest.raises(TypeError, match="Length must be an integer"):                                                           +
             generate_password(length="16")                                                                                          +

     def test_length_none_raises_type_error(self):                                                                                   +
         with pytest.raises(TypeError, match="Length must be an integer"):                                                           +
             generate_password(length=None)                                                                                          +

     def test_length_bool_raises_type_error(self):                                                                                   +
         """Booleans are technically ints in Python but should be rejected."""                                                       +
         with pytest.raises(TypeError, match="Length must be an integer"):                                                           +
             generate_password(length=True)                                                                                          +


 # ---------------------------------------------------------------------------                                                       +
 # Input validation – boolean flag types                                                                                             +
 # ---------------------------------------------------------------------------                                                       +

 class TestFlagValidation:                                                                                                           +
     """Test that invalid flag values raise appropriate exceptions."""                                                               +

     def test_include_special_int_raises_type_error(self):                                                                           +
         with pytest.raises(TypeError, match="include_special must be a boolean"):                                                   +
             generate_password(length=16, include_special=1)                                                                         +

     def test_include_special_string_raises_type_error(self):                                                                        +
         with pytest.raises(TypeError, match="include_special must be a boolean"):                                                   +
             generate_password(length=16, include_special="yes")                                                                     +

     def test_include_special_none_raises_type_error(self):                                                                          +
         with pytest.raises(TypeError, match="include_special must be a boolean"):                                                   +
             generate_password(length=16, include_special=None)                                                                      +

     def test_include_numbers_int_raises_type_error(self):                                                                           +
         with pytest.raises(TypeError, match="include_numbers must be a boolean"):                                                   +
             generate_password(length=16, include_numbers=1)                                                                         +

     def test_include_numbers_string_raises_type_error(self):                                                                        +
         with pytest.raises(TypeError, match="include_numbers must be a boolean"):                                                   +
             generate_password(length=16, include_numbers="yes")                                                                     +

     def test_include_numbers_none_raises_type_error(self):                                                                          +
         with pytest.raises(TypeError, match="include_numbers must be a boolean"):                                                   +
             generate_password(length=16, include_numbers=None)                                                                      +


 # ---------------------------------------------------------------------------                                                       +
 # Edge cases                                                                                                                        +
 # ---------------------------------------------------------------------------                                                       +

 class TestEdgeCases:                                                                                                                +
     """Test boundary and corner-case scenarios."""                                                                                  +

     def test_length_one_valid(self):                                                                                                +
         """Minimum valid length should work."""                                                                                     +
         password = generate_password(length=1)                                                                                      +
         assert len(password) == 1                                                                                                   +
         assert password.isprintable()                                                                                               +

     def test_length_128_valid(self):                                                                                                +
         """Maximum valid length should work."""                                                                                     +
         password = generate_password(length=128)                                                                                    +
         assert len(password) == 128                                                                                                 +

     def test_length_one_letters_only(self):                                                                                         +
         """Single character with no extras should be a letter."""                                                                   +
         password = generate_password(length=1, include_special=False, include_numbers=False)                                        +
         assert password in string.ascii_uppercase + string.ascii_lowercase                                                          +

     def test_contains_uppercase(self):                                                                                              +
         """A long password with all options should contain uppercase letters."""                                                    +
         password = generate_password(length=64, include_special=True, include_numbers=True)                                         +
         assert any(c in string.ascii_uppercase for c in password)                                                                   +

     def test_contains_lowercase(self):                                                                                              +
         """A long password with all options should contain lowercase letters."""                                                    +
         password = generate_password(length=64, include_special=True, include_numbers=True)                                         +
         assert any(c in string.ascii_lowercase for c in password)

