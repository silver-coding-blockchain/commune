

from typing import *
import asyncio
import commune as c
import aiohttp
import json



class Client(c.Module):
    count = 0
    def __init__( 
            self,
            address : str = '0.0.0.0:8000',
            network: bool = 'local',
            key : str = None,
            save_history: bool = True,
            history_path : str = 'history',
            loop: 'asyncio.EventLoop' = None, 
            debug: bool = False,
            serializer= 'serializer',
            default_fn = 'info',

            **kwargs
        ):
        self.loop = c.get_event_loop() if loop == None else loop
        self.serializer = c.module(serializer)()
        self.key = c.get_key(key)
        self.start_timestamp = c.timestamp()
        self.save_history = save_history
        self.history_path = history_path
        self.debug = debug
        self.default_fn = default_fn
        self.set_client(address = address, network=network)


    def process_input(self, args: list = None, kwargs: dict = None, params=None, message_type = "v0"):

        if isinstance(args, dict):
            kwargs = args
            argsf = None

        if params != None:
            assert type(params) in [list, dict], f'params must be a list or dict, not {type(params)}'
            if isinstance(params, list):
                args = params
            elif isinstance(params, dict):
                kwargs = params  
        kwargs = kwargs or {}
        args = args if args else []
        kwargs = kwargs if kwargs else {}
        
        # serialize this into a json string
        if message_type == "v0":
            """
            {
                'data' : {
                'args': args,
                'kwargs': kwargs,
                'timestamp': timestamp,
                }
                'signature': signature
            }
            
            """

            input =  { 
                        "args": args,
                        "kwargs": kwargs,
                        "timestamp": c.timestamp(),
                        }
            input = self.serializer.serialize(input)
            input = self.key.sign(input, return_json=True)
            # key emoji 
        elif message_type == "v1":
            input = {
                'params': kwargs,
                'access_token': self.key.ticket()
            }
            if len(args) > 0:
                input['args'] = args
            input = self.serializer.serialize(input)
        else:
            raise ValueError(f"Invalid message_type: {message_type}")

        return input
    
    def iter_over_async(self, ait):
        # helper async fn that just gets the next element
        # from the async iterator
        def get_next():
            try:
                obj = self.loop.run_until_complete(ait.__anext__())
                return obj
            except StopAsyncIteration:
                return 'done'
        # actual sync iterator (implemented using a generator)
        while True:
            obj = get_next() 
            if obj == 'done':
                break
            yield obj
        
    
    def process_stream_line(self, line ):
        STREAM_PREFIX = 'data: '
        event_data = line.decode('utf-8')
        event_data = event_data[len(STREAM_PREFIX):] if event_data.startswith(STREAM_PREFIX) else event_data
        event_data = event_data.strip() # remove leading and trailing whitespaces
        if event_data == "": # skip empty lines if the event data is empty
            return ''
        if isinstance(event_data, str):
            if event_data.startswith('{') and event_data.endswith('}') and 'data' in event_data:
                event_data = json.loads(event_data)['data']
        return event_data


    async def stream_generator(self, response):
        async for line in response.content:
            event =  self.process_stream_line(line)
            if event == '':
                continue
            yield event

    async def send_request(self, url:str, 
                           request: dict, 
                           headers=None, 
                           timeout:int=10, 
                           stream = False,
                           verbose=False):
        # start a client session and send the request
        c.print(f"🛰️ Call {url} 🛰️  (🔑{self.key.ss58_address})", color='green', verbose=verbose)
        if not hasattr(self, 'session'):
            self.session = aiohttp.ClientSession()
        response =  await self.session.post(url, json=request, headers=headers)
        if response.content_type == 'application/json':
            result = await asyncio.wait_for(response.json(), timeout=timeout)
        elif response.content_type == 'text/plain':
            result = await asyncio.wait_for(response.text(), timeout=timeout)
        elif response.content_type == 'text/event-stream':
            if stream:           
                return self.stream_generator(response)
            else:
                result = []  
                async for line in response.content:
                    event =  self.process_stream_line(line)
                    if event == '':
                        continue
                    result += [event]
                # process the result if its a json string
                if isinstance(result, str):
                    if (result.startswith('{') and result.endswith('}')) or result.startswith('[') and result.endswith(']'):
                        result = ''.join(result)
                        result = json.loads(result)
        
        else:
            raise ValueError(f"Invalid response content type: {response.content_type}")

        
        return result


    def process_output(self, result):
        ## handles 
        if isinstance(result, str):
            result = json.loads(result)
        if 'data' in result:
            result = self.serializer.deserialize(result)
            return result['data']
        else:
            return result


    def resolve_key(self,key=None):
        if key == None:
            key = self.key
        if isinstance(key, str):
            key = c.get_key(key)
        return key
    
    def resolve_url(self, address:str, fn:str):
        """
        params: 
            address: str : the address of the server
            fn: str : the function name
        returns:
            url: str : the url to call
        """
        address = address or self.address
        fn = fn or self.default_fn
        if '/' in address.split('://')[-1]:
            address = address.split('://')[-1]
        url = f"{address}/{fn}/"
        url = 'http://' + url if not url.startswith('http://') else url

        return url
    

    def forward(self, *args, **kwargs):
        return self.loop.run_until_complete(self.async_forward(*args, **kwargs))

    def process_output(self, output):
        """
        params:
            request: dict : the request that was sent
            result: any : the result that was returned

        """
        if type(output) in [str, dict, int, float, list, tuple, set, bool, type(None)]:
            output = self.serializer.deserialize(output)
            if isinstance(output, dict) and 'data' in output:
                output = output['data']
        else: 
            output = self.iter_over_async(output)
        
        return output

    async def async_forward(self,
        fn: str,
        params: dict = None,
        args: list = None,
        kwargs: dict = None,
        address : str = None,
        timeout: int = 10,
        headers : dict ={'Content-Type': 'application/json'},
        message_type = "v0",
        key : str = None,
        verbose = False,
        stream = False,
        **extra_kwargs
        ):

        """
        params: 
            fn: str : the function name
            params: dict : the parameters to pass to the function
            args: list : the arguments to pass to the function
            kwargs: dict : the keyword arguments to pass to the function
            address: str : the address of the server
            timeout: int : the timeout for the request
            headers: dict : the headers to pass to the request
            message_type: str : the message type to use
            key: str : the key to use
            verbose: bool : whether to print the request
            stream: bool : whether to stream the response
            ----------
            **extra_kwargs: dict : extra kwargs to pass to the request
        """

        try:
            key = self.resolve_key(key)
            url = self.resolve_url(address, fn)
            kwargs ={**(kwargs or {}), **extra_kwargs}
            input = self.process_input(args=args, kwargs=kwargs, params=params, message_type=message_type)
            output = await asyncio.wait_for(self.send_request(url=url, request=input, headers=headers, verbose=verbose, stream=stream), timeout=timeout)
            output = self.process_output(output)

            if self.save_history:
                path =  self.history_path+ '/' + self.key.ss58_address + '/' + self.address+ '/'+  str(c.timestamp())
                self.put(path, { 'input': input, 'output': output })
        except Exception as e:
            output = c.detailed_error(e)

        return output


    def __del__(self):
        if hasattr(self , 'session'):
            self.loop.run_until_complete(self.session.close())
    
    def age(self):
        return  self.start_timestamp - c.timestamp()

    def set_client(self,
            address : str = None,
            verbose: bool = 1,
            network : str = 'local',
            possible_modes = ['http', 'https'],
            ):
        # we dont want to load the namespace if we have the address
        if not c.is_address(address):
            module = address # we assume its a module name
            assert module != None, 'module must be provided'
            namespace = c.get_namespace(search=module, network=network)
            if module in namespace:
                address = namespace[module]
            else:    
                address = module
        if '://' in address:
            mode = address.split('://')[0]
            assert mode in possible_modes, f'Invalid mode {mode}'
            address = address.split('://')[-1]
        address = address.replace(c.ip(), '0.0.0.0')
        self.address = address
        return {'address': self.address}

    @classmethod
    def history(cls, key=None, history_path='history'):
        key = c.get_key(key)
        return cls.ls(history_path + '/' + key.ss58_address)
    


    @classmethod
    def call(cls, 
                module : str, 
                fn:str = None,
                *args,
                kwargs = None,
                params = None,
                prefix_match:bool = False,
                network:str = 'local',
                key:str = None,
                stream = False,
                timeout=40,
                **extra_kwargs) -> None:
          
        # if '
        if '//' in module:
            module = module.split('//')[-1]
            mode = module.split('//')[0]
        if '/' in module:
            if fn != None:
                args = [fn] + list(args)
            module , fn = module.split('/')

        module = cls.connect(module,
                           network=network,  
                           prefix_match=prefix_match, 
                           virtual=False, 
                           key=key)

        if params != None:
            kwargs = params

        if kwargs == None:
            kwargs = {}

        kwargs.update(extra_kwargs)

        return  module.forward(fn=fn, args=args, kwargs=kwargs, stream=stream, timeout=timeout)

    @classmethod
    def call_search(cls, 
                    search : str, 
                *args,
                timeout : int = 10,
                network:str = 'local',
                key:str = None,
                kwargs = None,
                **extra_kwargs) -> None:
        if '/' in search:
            search, fn = search.split('/')
        namespace = c.namespace(search=search, network=network)
        future2module = {}
        for module, address in namespace.items():
            c.print(f"Calling {module}/{fn}", color='green')
            future = c.submit(cls.call,
                               args = [module, fn] + list(args),
                               kwargs = {'timeout': timeout, 
                                         'network': network, 'key': key, 
                                         'kwargs': kwargs,
                                         **extra_kwargs} , timeout=timeout)
            future2module[future] = module
        futures = list(future2module.keys())
        result = {}
        progress_bar = c.tqdm(len(futures))
        for future in c.as_completed(futures, timeout=timeout):
            module = future2module.pop(future)
            futures.remove(future)
            progress_bar.update(1)
            result[module] = future.result()

        return result
            

        
    __call__ = forward

    def __str__ ( self ):
        return "Client({})".format(self.address) 
    def __repr__ ( self ):
        return self.__str__()
    def __exit__ ( self ):
        self.__del__()

    def virtual(self):
        from .virtual import VirtualClient
        return VirtualClient(module = self)
    
    def __repr__(self) -> str:
        return super().__repr__()


    @classmethod
    def connect(cls,
                module:str, 
                network : str = 'local',
                mode = 'http',
                virtual:bool = True, 
                **kwargs):
        
        
        
        client = cls(address=module, 
                                       virtual=virtual, 
                                       network=network,
                                       **kwargs)
        # if virtual turn client into a virtual client, making it act like if the server was local
        if virtual:
            return client.virtual()
        
        return client
    

    def test(self, module='module::test_client'):
        c.serve(module)
        c.sleep(1)
        c.print(c.server_exists(module))
        c.print('Module started')

        info = c.call(module+'/info')
        key  = c.get_key(module)
        assert info['key'] == key.ss58_address
        return {'info': info, 'key': str(key)}

    def __del__(self):
        if hasattr(self, 'session'):
            asyncio.run(self.session.close())
