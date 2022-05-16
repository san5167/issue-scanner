import os
import re
import sys
from util.stack import Stack
import string


operator = { #前后顺序代表优先级
    'or': 3,
    'and': 3,
    'with': ValueError ,
    '(': ValueError,
    ')':ValueError,
}
priority = {}
x=2147483647
for i in list(operator):
    x-=1
    priority[i]=x

def infixToPostfix(infixexpr):
    operation_stack = Stack()
    postfix_list = []
 
    token_list = []
    license_set = re.split(r'\(|\)|\s+\,|\s+[Aa][Nn][Dd]\s+|\s+-?or-?\s+|\s+/\s+|\s+[Ww][Ii][Tt][Hh]\s+', infixexpr)
    posfix_set = re.findall(r'\(|\)|\s+\,|\s+[Aa][Nn][Dd]\s+|\s+-?or-?\s+|\s+/\s+|\s+[Ww][Ii][Tt][Hh]\s+', infixexpr)

    if len(posfix_set) == 0:
        return license_set

    for i,var in enumerate(posfix_set):
        token_list.append(license_set[i])
        token_list.append(posfix_set[i])
    
    token_list.append(license_set[len(license_set) - 1])

    for index in range(len(token_list)):  # 去除字符串首尾空格
        token_list[index] = token_list[index].strip()

    token_list = list(filter(None, token_list))
 
    for token in token_list:
        
        # 左括号入栈
        if token == '(':
            operation_stack.push(token)
        # 如果标记是右括号，反复从operation_stack栈中移除元素，
        # 直到移除对应的左括号
        elif token == ')':
            top_token = operation_stack.pop()
            while top_token != '(':
                # 将从栈中取出的每一个运算符都添加到结果列表的末尾
                postfix_list.append(top_token)
                top_token = operation_stack.pop()
        # 操作数添加到列表末尾
        elif token in ['and','or','with']:
            # postfix_list.append(token):
            while (not operation_stack.is_empty()) and (priority[operation_stack.peek()] >= priority[token]):
                postfix_list.append(operation_stack.pop())
            operation_stack.push(token)
        else:
            postfix_list.append(token)
 
    while not operation_stack.is_empty():
        postfix_list.append(operation_stack.pop())
 
    return postfix_list


    