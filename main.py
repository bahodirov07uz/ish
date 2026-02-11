class Solution:
    def __init__(self,s):
        # Instance attributes (unique to each instance)
        self.name = s
        
    def lengthOfLastWord(self, s: str) -> int:
        c = 0
        p = len(s) - 1
        n = 0
        for i in range(len(s)):
            if s[p] == " ":
                c  = 0
                n += 1
            while not s[p] == " " and n <= 2:
                c += 1
            p -= 1
        return c
    
    
a = Solution("hello ")

print(a.lengthOfLastWord("hello "))