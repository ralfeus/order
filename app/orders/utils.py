'''Sale orders related useful functions'''
from datetime import datetime
# import re

from sqlalchemy.exc import DataError

from exceptions import SubcustomerParseError
from .models.subcustomer import Subcustomer

def parse_subcustomer(subcustomer_data) -> tuple[Subcustomer, bool]:
    '''Returns a tuple of customer from raw data
    and indication whether customer is existing one or created
    
    :param str subcustomer_data: string in format <ID, Name, Password>
    :returns tuple[Subcustomer, bool]: tuple of Subcustomer object and boolean indicating if it was created'''
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
