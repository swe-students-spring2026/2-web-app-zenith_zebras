# Hardcoding user input for building purposes
# input1 = email input2 = password inpput3 = confirm password
import re # for confirm email function

def sign_up(input1, input2, input3):
    validation = validate_input(input1, input2, input3)
    if (validation == 1):
        email = input1
        password = input2
        user_name = email.split('@')[0]
        posts = []
        # store user info in database

        # Go to login page
        return redirect(url_for('login'))
    else:
        return return_error(validation)




def return_error(error_code):
    if (error_code == 2):
        # "Error: Password must be at least 8 characters long."
        return null
    elif (error_code == 3):
        #"Error: Password and confirm password do not match."
        return null
    elif (error_code == 4):
        #"Error: Email is not a valid NYU email address."
        return null
    else:
        # "Error: An unknown error occurred during sign up."
        return null

    



# This function checks that all sign in info is correct
def validate_input(email, password, confirm_password):
    # cast all inputs to string and check that they are strings
    email = str(email)
    password = str(password)
    confirm_password = str(confirm_password)
    # check that email is valid
    if (is_valid_nyu_email(email)):
        if (password == confirm_password):
            if (len(password) >=8):
                # proceed with sign in logic
                return 1
            else:
                return 2
        else:
            return 3
    else:
        return 4



def is_valid_nyu_email(email):
    if not isinstance(email, str):
        return False
    
    email = email.strip()
    pattern = r'^[A-Za-z0-9]+@nyu\.edu$'
    return re.fullmatch(pattern, email, re.IGNORECASE) is not None



def is_string(value):
    return isinstance(value, str)