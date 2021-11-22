'''Models for network manager'''
from datetime import date, datetime
from neotime import DateTime
from neomodel import StructuredNode, RelationshipTo, db
from neomodel.properties import BooleanProperty, DateProperty, IntegerProperty, \
    StringProperty, validator

class CustomDateProperty(DateProperty):
    """
    Stores a date
    """
    form_field_class = 'DateField'

    @validator
    def inflate(self, value):
        if isinstance(value, DateTime):
            value = date(value.year, value.month, value.day)
        elif isinstance(value, str):
            if "T" in value:
                value = value[:value.find('T')]
        return datetime.strptime(str(value), "%Y-%m-%d").date()

class AtomyPerson(StructuredNode):
    '''Atomy person object as it's saved in Neo4j'''
    atomy_id = StringProperty(unique_index=True, required=True)
    name = StringProperty()
    rank = StringProperty()
    highest_rank = StringProperty()
    center = StringProperty()
    country = StringProperty()
    signup_date = CustomDateProperty()
    pv = IntegerProperty()
    network_pv = IntegerProperty()
    '''Defines whether a tree for this node was already built or not
    Needed when the node has no children and shouldn't be traversed'''
    built_tree = BooleanProperty(default=False)
    parent_id = None
    parent = RelationshipTo('AtomyPerson', 'PARENT')
    right_id = None
    right_child = RelationshipTo('AtomyPerson', 'RIGHT_CHILD')
    left_id = None
    left_child = RelationshipTo('AtomyPerson', 'LEFT_CHILD')

    @classmethod
    def inflate(cls, node):
        '''Augments base inflate() with parent and children'''
        person = super().inflate(node[0])
        relatives = person.cypher('''
            MATCH (n:AtomyPerson) WHERE id(n) = $self
            OPTIONAL MATCH (n)-[:PARENT]->(p) 
            OPTIONAL MATCH (n)-[:LEFT_CHILD]->(l)
            OPTIONAL MATCH (n)-[:RIGHT_CHILD]->(r)
            RETURN p.atomy_id, l.atomy_id, r.atomy_id
        ''')[0][0]
        person.parent_id = relatives[0]
        person.left_id = relatives[1]
        person.right_id = relatives[2]
        return person

    def to_dict(self):
        '''Returns dict representation of the object'''
        mapping = {'atomy_id': 'id'}
        return {
            **{
                mapping.get(attr[0]) or attr[0]: self.__getattribute__(attr[0])
                for attr in self.__all_properties__
            },
            'parent_id': self.parent_id,
            'right_id': self.right_id,
            'left_id': self.left_id
        }
