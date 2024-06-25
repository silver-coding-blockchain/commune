
from .module import Module
c = Block = Lego = M = Module  # alias c.Module as c.Block, c.Lego, c.M
from .cli import cli
from .vali.vali import Vali
from .tree.tree import Tree
from .client.client import Client
from .server.server import Server
from .namespace import Namespace
# import sys
# sys.path += [c.pwd()]

# from .modules.subspace import subspace
# from .model import Model

# set the module functions as globals
for k,v in Module.__dict__.items():
    globals()[k] = v
for f in Module.class_functions() + Module.static_functions():
    globals()[f] = getattr(Module, f)
for f in Module.self_functions():
    globals()[f] = lambda *args, **kwargs: getattr(Module(), f)(*args, **kwargs)
globals()['cli'] = cli

