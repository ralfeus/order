from marshmallow import Schema, fields

class FilterSchema(Schema):
    pass

class PagingSchema(Schema):
    page = fields.Integer()
    page_size = fields.Integer()

class NodeSchema(Schema):
    filter = fields.Nested(FilterSchema)
    paging = fields.Nested(PagingSchema)
    start = fields.Integer()
    limit = fields.Integer()