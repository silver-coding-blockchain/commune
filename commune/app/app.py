import commune as c
import os
import json
import streamlit as st
from typing import *

class App(c.Module):
    port_range = [8501, 8600]
    name_prefix = 'app::'

    def start(self,
           module:str = 'server', 
           name : Optional[str] = None,
           fn:str='app', 
           port:int=None, 
           remote:bool = True, 
           kwargs:dict=None, 
           app_info:dict=None,
           update:bool=False,
           **extra_kwargs):
        if app_info == None:
            app_info = self.app2info().get(name, {})
            kwargs = kwargs or {}
            port = port or c.free_port()
            name = name or app_info.get('name',  self.name_prefix +module) 
            port = port or app_info.get('port', c.free_port())
            if c.port_used(port):
                c.kill_port(port)
            if c.module_exists(module + '.app'):
                module = module + '.app'

            module = c.module(module)
            # add port to the command
            cmd = f'streamlit run {module.filepath()} --server.port {port}'
            kwargs_str = json.dumps(kwargs or {}).replace('"', "'")
            cmd += f' -- --fn {fn} --kwargs "{kwargs_str}"'
            app_info= {
                'name': name,
                'port': port,
                'fn': fn,
                'kwargs': kwargs,
                'cmd': cmd, 
                'cwd': os.path.dirname(module.filepath()),
            }
        
        if remote:
            c.remote_fn(module=module, 
                        fn='start_app',
                        name=name,
                        kwargs= {'app_info': app_info, 'remote': False})
            return app_info 
        cmd = app_info['cmd']
        cwd  = app_info['cwd']
        name = app_info['name']
        c.cmd(cmd, verbose=True, cwd=cwd)
        app2info = self.app2info()
        app2info[name] = app_info
        self.put('app2info', app2info)
        return app_info
    start_app = app = start
    def app2info(self):
        app2info =  self.get('app2info', {})
        if not isinstance(app2info, dict):
            app2info = {}
        return app2info
    

    def kill_all(self):
        return c.module('pm2').kill_many(self.apps())
    
    def kill(self, name):
        return c.module('pm2').kill(self.name_prefix+name)
    
    def filter_name(self, name:str) -> bool:
        return bool(name.startswith(self.name_prefix))
        
    def apps(self, remove_prefix = True):
        apps =  [n for n in c.pm2ls() if n.startswith(self.name_prefix)]
        if remove_prefix:
            apps = [n[len(self.name_prefix):] for n in apps]
        return apps
    


    
    

App.run(__name__)
    

c