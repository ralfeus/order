'''Models for network manager'''
from datetime import date, datetime
import neo4j.time
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
        if isinstance(value, neo4j.time.DateTime):
            return date(value.year, value.month, value.day)
        if isinstance(value, str):
            if "T" in value:
                value = value[:value.find('T')]
            return date(int(value[:4]), int(value[5:7]), int(value[8:10]))
        raise Exception(f"Unknown format: {value}")

class AtomyPerson(StructuredNode):
    '''Atomy person object as it's saved in Neo4j'''
    atomy_id = StringProperty(unique_index=True, required=True)
    password = StringProperty()
    name = StringProperty()
    rank = StringProperty()
    highest_rank = StringProperty()
    center = StringProperty()
    country = StringProperty()
    signup_date = CustomDateProperty()
    pv = IntegerProperty()
    total_pv = IntegerProperty()
    network_pv = IntegerProperty()
    '''Defines whether a tree for this node was already built or not
    Needed when the node has no children and shouldn't be traversed'''
    built_tree = BooleanProperty(default=False)
    when_updated = CustomDateProperty()
    _relatives_are_set = False
    _parent_id = None
    parent = RelationshipTo('AtomyPerson', 'PARENT')
    _right_id = None
    right_child = RelationshipTo('AtomyPerson', 'RIGHT_CHILD')
    _left_id = None
    left_child = RelationshipTo('AtomyPerson', 'LEFT_CHILD')

    @classmethod
    def inflate(cls, node, lazy=True):
        '''Augments base inflate() with parent and children'''
        person = super().inflate(node)
        if not lazy:
            person._set_relatives()
        return person

    def _set_relatives(self):
        relatives = self.cypher('''
            MATCH (n:AtomyPerson) WHERE id(n) = $self
            OPTIONAL MATCH (n)-[:PARENT]->(p) 
            OPTIONAL MATCH (n)-[:LEFT_CHILD]->(l)
            OPTIONAL MATCH (n)-[:RIGHT_CHILD]->(r)
            RETURN p.atomy_id, l.atomy_id, r.atomy_id
        ''')[0][0]
        self._parent_id = relatives[0]
        self._left_id = relatives[1]
        self._right_id = relatives[2]
        self._relatives_are_set = True
    
    @property
    def parent_id(self):
        '''A parent_id property. Gets value from DB is necessary'''
        if self._parent_id is None and not self._relatives_are_set:
            self._set_relatives()
        return self._parent_id
        
    @property
    def left_id(self):
        '''A parent_id property. Gets value from DB is necessary'''
        if self._left_id is None and not self._relatives_are_set:
            self._set_relatives()
        return self._left_id

    @property
    def right_id(self):
        '''A parent_id property. Gets value from DB is necessary'''
        if self._right_id is None and not self._relatives_are_set:
            self._set_relatives()
        return self._right_id

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
