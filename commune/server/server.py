import commune as c
import pandas as pd
from typing import *
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


class Server(c.Module):
    def __init__(
        self,
        module: Union[c.Module, object] = None,
        name: str = None,
        network:str = 'local',
        port: Optional[int] = None,
        key = None,
        protocal = 'server.protocal',
        save_history:bool= True,
        history_path:str = None , 
        nest_asyncio = True,
        new_loop = True,
        **kwargs
        ) -> 'Server':
        """
        
        params:
        - module: the module to serve
        - name: the name of the server
        - port: the port of the serve
        
        """

        if new_loop:
            c.new_event_loop(nest_asyncio=nest_asyncio)
        self.set_module(module=module, 
                        name=name, 
                        port=port, 
                        key=key, 
                        protocal=protocal, 
                        save_history=save_history,
                        history_path=history_path,
                        network=network, **kwargs
                        )
        self.set_api()

    def set_module(self, 
                   module: Union[c.Module, object] = None, 
                   name: str = None, 
                   port: Optional[int] = None, 
                   key = None, 
                   protocal = 'server.protocal', 
                   save_history:bool= False, 
                   history_path:str = None, 
                   network:str = 'local',
                   **kwargs
                   ):
        

        self.protocal = c.module(protocal)(module=module,     
                                            history_path=self.resolve_path(history_path  or name),
                                            name = name,
                                            port=port,
                                            key=key,
                                            save_history = save_history,
                                             **kwargs)
        self.module = self.protocal.module 
        response = {'name':self.module.name, 'address': self.module.address, 'port':self.module.port, 'key':self.module.key.ss58_address, 'network':self.module.network, 'success':True}
        return response

    def add_fn(self, name:str, fn: str):
        assert callable(fn), 'fn not callable'
        setattr(self.module, name, fn)
        return {'success':True, 'message':f'Added {name} to {self.name} module'}
           
    def set_api(self):

        self.app = FastAPI()
        self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        
        @self.app.post("/{fn}")
        def forward_api(fn:str, input:dict):
            return self.protocal.forward(fn=fn, input=input)
        
        # start the server
        try:
            c.print(f' Served(name={self.module.name}, address={self.module.address}, key=🔑{self.module.key}🔑 ) 🚀 ', color='purple')
            c.register_server(name=self.module.name, address = self.module.address, network=self.module.network)
            uvicorn.run(self.app, host='0.0.0.0', port=self.module.port, loop="asyncio")
        except Exception as e:
            c.print(e, color='red')
        finally:
            c.deregister_server(self.name, network=self.module.network)

    def info(self) -> Dict:
        return {
            'name': self.module.name,
            'address': self.module.address,
            'key': self.module.key.ss58_address,
            'network': self.module.network,
            'port': self.module.port,
            'whitelist': self.module.whitelist,
            'blacklist': self.module.blacklist,            
        }

    def __del__(self):
        c.deregister_server(self.name)
    

    @classmethod
    def serve_many(cls, modules:list, **kwargs):

        if isinstance(modules[0], list):
            modules = modules[0]
        
        futures = []
        for module in modules:
            future = c.submit(c.serve, kwargs={'module': module, **kwargs})
            futures.append(future)
            
        results = []
        for future in c.as_completed(futures):
            result = future.result()
            c.print(result)
            results.append(result)
        return results
    serve_batch = serve_many


    @classmethod
    def serve(cls, 
              module:Any ,
              kwargs:dict = None,  # kwargs for the module
              tag:str=None,
              server_network = 'local',
              port :int = None, # name of the server if None, it will be the module name
              server_name:str=None, # name of the server if None, it will be the module name
              name = None, # name of the server if None, it will be the module name
              refresh:bool = True, # refreshes the server's key
              tag_seperator:str='::',
              max_workers:int = None,
              free: bool = False,
              mnemonic = None, # mnemonic for the server
              key = None,
              **extra_kwargs
              ):
        kwargs = kwargs or {}
        kwargs.update(extra_kwargs or {})
        name = server_name or name # name of the server if None, it will be the module name
        if '::' in module:
            name = module
            module, tag = module.split('::')
        name = name or module
        # RESOLVE THE PORT FROM THE ADDRESS IF IT ALREADY EXISTS
        namespace = c.namespace(network=server_network)
        if port == None and name in namespace:
            address = namespace.get(name, None)
            port = int(address.split(':')[-1]) if address else c.free_port()
        if port == None:
            port = c.free_port()
            
        module_class = c.module(module)

        if mnemonic != None:
            c.add_key(server_name, mnemonic)
        key = key or server_name
        if not c.key_exists(key):
            c.add_key(key)
        self = module_class(**kwargs)
        if c.server_exists(server_name, network=server_network) and not refresh: 
            return {'success':True, 'message':f'Server {server_name} already exists'}
        else:
            c.kill(server_name, network=server_network)
        
        c.module(f'server')(module=self, 
                                          name=name, 
                                          port=port, 
                                          network=server_network, 
                                          max_workers=max_workers, 
                                          free=free, 
                                          key=key)

        return  {'success':True, 
                     'address':  f'{c.default_ip}:{port}' , 
                     'name':name, 
                     'kwargs': kwargs,
                     'module':module}
    
    @classmethod
    def history(cls, **kwargs):
        return c.ls(c.resolve_path('history'))

Server.run(__name__)