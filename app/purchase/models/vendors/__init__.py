import importlib
import glob
from os.path import dirname, basename, isfile, join, splitext
import sys
from .vendor_base import PurchaseOrderVendorBase

self = sys.modules[__name__]
__all__ = []
vendors = []
modules = [ f
    for f in glob.glob(join(dirname(__file__), "*.py"))
    if isfile(f) and not f.endswith('__init__.py')
        # and not f.endswith('purchase_order_manager.py')
]
for module in modules:
    # with open(module, 'rb') as fp:
        module_name = splitext(basename(module))[0]
        # res = imp.find_module(splitext(basename(module))[0], __path__)
        # print(res)
        ma = importlib.import_module(
            __name__ + '.' + module_name, 
            module)
        # print(ma)  
        classes = { c for c in ma.__dict__.items()
            if isinstance(c[1], type) and issubclass(c[1], PurchaseOrderVendorBase) }
        for class_pair in classes:
            setattr(self, class_pair[0], class_pair[1])
            if class_pair[0] not in __all__:
                __all__.append(class_pair[0])
                if issubclass(class_pair[1], PurchaseOrderVendorBase):
                    vendors.append(class_pair[1])
        # print({c[0]: type(c[1]) for c in classes})
