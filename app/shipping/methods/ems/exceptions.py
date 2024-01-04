class EMSItemsException(Exception):
    def __str__(self):
        return f"<EMSItemsException: {self.args}>"