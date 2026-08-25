 from generator import generate_password+


 def main():                            +
     args = parse_args()                +
     password = generate_password(      +
         length=args.length,            +
         include_special=args.special,  +
         include_numbers=args.numbers,  +
     )                                  +
     print(password)                    +


 if __name__ == "__main__":             +
     main()

