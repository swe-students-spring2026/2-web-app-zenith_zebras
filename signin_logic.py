# Hardcoding user input for building purposes
# input1 = email input2 = password inpput3 = confirm password
import re # for confirm email function

if (create_user(input1, input2, input3)):
    email = input1
    password = input2
    user_name = email.split('@')[0]
    posts = []
    # store user info in database
    # Go to login page


# This function checks that all sign in info is correct
def create_user(email, password, confirm_password):
    if (is_string(email) and is_string(password) and is_string(confirm_password)):
        # check that email is valid
        if (is_valid_nyu_email(email)):
            if (password == confirm_password):
                if (len(password) >=8):
                    # proceed with sign in logic
                    return True
                    print("Sign in successful!")
                else:
                    print("Error: Password must be at least 8 characters long.")
            else:
                print("Error: Password and confirm password do not match.")
        else:
            print("Error: Email is not a valid NYU email address.")
    else:
        print("Error: All inputs must be strings.")


def is_valid_nyu_email(email):
    if not isinstance(email, str):
        return False
    
    email = email.strip()
    pattern = r'^[A-Za-z0-9]+@nyu\.edu$'
    return re.fullmatch(pattern, email, re.IGNORECASE) is not None




def is_string(value):
    return isinstance(value, str)