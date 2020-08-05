from io import BytesIO
import openpyxl

def get_order_from_file(file):
    order_data = file.read()
    wb = openpyxl.load_workbook(BytesIO(order_data))
    wb.sheetnames
