import commune as c
from typing import *

class Text(c.Module):
    def __init__(self, a=1, b=2):
        self.set_config(kwargs=locals())

    def substring_count_in_string(self, string, substring):
        return str(string).count(str(substring))
    
    def call(self, text, fn='model.openai/generate', **kwargs):
        return c.call(fn, text, **kwargs)
    

    def text2lines(self, text):
        return text.splitlines()
    
    def get_text(self, text, start, end):
        return text[start:end]
    

    def search2lines(self, filepath=None, search='search' ):
        text = c.get_text(filepath or self.filepath())
        return {i: line for i,line in enumerate(text.splitlines()) if search in line}
        


    @classmethod
    def find_lines(self, text:str, search:str) -> List[str]:
        """
        Finds the lines in text with search
        """
        found_lines = []
        lines = text.split('\n')
        for line in lines:
            if search in line:
                found_lines += [line]
        
        return found_lines