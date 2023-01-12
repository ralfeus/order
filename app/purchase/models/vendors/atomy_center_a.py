from app.purchase.models.vendors.atomy_center import AtomyCenter


class AtomyCenterA(AtomyCenter):
    _username = 'atomy2327'
    _password = '0507'

    def __str__(self):
        return "Atomy - Center - A"