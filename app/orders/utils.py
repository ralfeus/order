'''Sale orders related useful functions'''
from datetime import datetime
# import re

from sqlalchemy.exc import DataError

from exceptions import SubcustomerParseError
from .models import Subcustomer

def parse_subcustomer(subcustomer_data):
    '''Returns a tuple of customer from raw data
    and indication whether customer is existing one or created'''
    parts = subcustomer_data.split(',', 2)
    try:
        subcustomer = Subcustomer.query.filter(
            Subcustomer.username == parts[0].strip()).first()
        if subcustomer:
            if len(parts) >= 2 and subcustomer.name != parts[1].strip():
                subcustomer.name = parts[1].strip()
            if len(parts) == 3 and subcustomer.password != parts[2].strip():
                subcustomer.password = parts[2].strip()
            return subcustomer, False
    except DataError as ex:
        pass
        # message = ex.orig.args[1]
        # match = re.search('(INSERT INTO|UPDATE) (.+?) ', ex.statement)
        # if match:
        #     table = match.groups()[1]
        #     if table:
        #         if table == 'subcustomers':
        #             message = "Subcustomer error: " + message + " " + str(ex.params[2:5])
        #     result = {
        #         'status': 'error',
        #         'message': f"""Couldn't parse the subcustomer due to input error. Check your form and try again.
        #                     {message}"""
        #     }
    except IndexError:
        pass # the password wasn't provided, so we don't update
    try:
        subcustomer = Subcustomer(
            username=parts[0].strip(),
            name=parts[1].strip(),
            password=parts[2].strip(),
            when_created=datetime.now())
        # db.session.add(subcustomer)
        return subcustomer, True
    except ValueError as ex:
        raise SubcustomerParseError(str(ex))
    except IndexError:
        raise SubcustomerParseError("The subcustomer string doesn't conform <ID, Name, Password> format")
