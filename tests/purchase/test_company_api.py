from datetime import datetime

from app.users.models.role import Role
from app.users.models.user import User
from app.purchase.models.company import Company
from app.models.address import Address
from tests import BaseTestCase, db

class TestCompanyClient(BaseTestCase):
    def setUp(self):
        super().setUp()
        db.create_all()
        
        admin_role = Role(id=10, name='admin')
        self.user = User(id=10, username='user1_test_company_api', email='user_test_company_api@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576', 
                enabled=True)
        self.admin = User(username='root_test_company_api', email='root_test_company_api@name.com',
                password_hash='pbkdf2:sha256:150000$bwYY0rIO$320d11e791b3a0f1d0742038ceebf879b8182898cbefee7bf0e55b9c9e9e5576',
                enabled=True, roles=[admin_role])
        self.try_add_entities([ self.user, self.admin, admin_role ])

    def try_admin_operation(self, operation):
        '''
        Superseeds base method to add class-specific user and admin credentials
        '''
        return super().try_admin_operation(
            operation,
            'user1_test_company_api', '1', 'root_test_company_api', '1')

    def test_get_company(self):
        self.try_add_entities([
            Address(id=123, name='Address_1'),
            Company(name='Company_1', tax_id_1='123', tax_id_2='12', tax_id_3='12345',phone='012-1234-1234',address_id=123,bank_id='01',contact_person='person1')
        ])
        res = self.try_admin_operation(
            lambda: self.client.get('/api/v1/admin/purchase/company'))
        self.assertEqual(res.json[0], {
            'id': 1,
            'name': 'Company_1',
            'tax_id': '123-12-12345',
            'phone': '012-1234-1234',
            'address': {
                'id': 123,
                'name': 'Address_1',
                'address_1': None,
                'address_2': None,
                'zip': None,
                'address_1_eng': None,
                'address_2_eng': None,
                'city_eng': None,
                'delivery_comment': None
            },
            'bank_id': '01',
            'contact_person': 'person1',
            'business_category': None,
            'business_type': None,
            'email': None,
            'tax_address': None,
            'tax_phone': None,
            'tax_simplified': True,
            'default': False,
            'enabled': True
        })

    def test_create_company(self):
        self.try_add_entities([
            Address(id=123, name='Address 1')])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/purchase/company',
            json={'name': 'Company_1', 'tax_id': '', 'address_id': 123})
        )
        self.assertEqual(res.status_code, 200)

    def test_save_company(self):
        gen_id = int(datetime.now().timestamp())
        self.try_add_entities([
            Address(id=123, name='Address 1'),
            Company(id=gen_id, name='Company_1', tax_id_1='123',tax_id_2='12',tax_id_3='12345', phone='012-1234-1234',address_id=123,bank_id='01',contact_person='person1')
        ])
        res = self.try_admin_operation(
            lambda: self.client.post(f'/api/v1/admin/purchase/company/{gen_id}',
            json={'name': 'Company_2', 'tax_id': '111-11-11111'})
        )
        self.assertEqual(res.status_code, 200)
        company = Company.query.get(gen_id)
        self.assertEqual(company.name, 'Company_2')

        # res = self.client.post(f'/api/v1/admin/company/{gen_id}',
        #     json={'bank_id': '01@', 'tax_id': '111-11-11111'})
        # self.assertEqual(res.status_code, 400)

    
    def test_delete_company(self):
        gen_id = int(datetime.now().timestamp())
        self.try_add_entities([
            Address(id=123, name='Address 1'),
            Company(id=gen_id, name='Company_1', tax_id_1='123', tax_id_2='12', tax_id_3='12345',phone='012-1234-1234',address_id=123,bank_id='01',contact_person='person1')
        ])
        res = self.try_admin_operation(
            lambda: self.client.delete(f'/api/v1/admin/purchase/company/{gen_id}')
        )
        self.assertEqual(res.status_code, 200)
        company = Company.query.get(gen_id)
        self.assertEqual(company, None)
    