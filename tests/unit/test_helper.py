import re
import unittest
import sys
import os.path
from collections import namedtuple
import binascii
sys.path.append('./tests')
sys.path.append('./src')

from common.disassembler import parser_disassembler
from decompiler import decompiler_t
from output import c
import ssa
from expressions import *
import host.dis

try:
  import capstone
except ImportError as e:
  print 'warning: Capstone tests are unavailable'
  pass

class TestHelper(unittest.TestCase):

  def __init__(self, *args):
    unittest.TestCase.__init__(self, *args)
    self.disasm = None
    self.maxDiff = None
    return

  def unindent(self, text):
    text = re.sub(r'^[\s]*\n', '', text)
    text = re.sub(r'\n[\s]*$', '', text)
    lines = text.split("\n")
    indents = [re.match(r'^[\s]*', line) for line in lines if line.strip() != '']
    lengths = [(len(m.group(0)) if m else 0) for m in indents]
    indent = min(lengths) if len(lengths) > 0 else 0
    unindented = [line[indent:] for line in lines]
    return "\n".join(unindented)

  def deep_tokenize(self, flow, input):

    if isinstance(input, dict):
      tokenized = {}
      for left, right in input.iteritems():
        tkey =self.deep_tokenize(flow, left)
        tokenized[tkey] = self.deep_tokenize(flow, right)
      return tokenized
    elif isinstance(input, list):
      return [self.deep_tokenize(flow, expr) for expr in input]
    elif isinstance(input, assignable_t) or isinstance(input, expr_t):
      t = c.tokenizer(flow)
      tokens = list(t.expression_tokens(input))
      return ''.join([str(t) for t in tokens])
    elif isinstance(input, value_t):
      t = c.tokenizer(flow)
      tokens = list(t.expression_tokens(input))
      return ''.join([str(t) for t in tokens])
    else:
      return repr(input)

    raise

  @staticmethod
  def disasm_capstone_x86(test_func):
    def disasm_capstone_x86_wrapper(self, *args):
      self.disasm = 'capstone-x86'
      test_func(self, *args)
      self.disasm = None
    return disasm_capstone_x86_wrapper

  @staticmethod
  def disasm_capstone_x86_64(test_func):
    def disasm_capstone_x86_64_wrapper(self, *args):
      self.disasm = 'capstone-x86-64'
      test_func(self, *args)
      self.disasm = None
    return disasm_capstone_x86_64_wrapper

  @staticmethod
  def disasm_ir_parser(test_func):
    def disasm_ir_parser_wrapper(self, *args):
      self.disasm = 'ir-parser'
      test_func(self, *args)
      self.disasm = None
    return disasm_ir_parser_wrapper

  def decompile_until(self, input, last_step):

    ssa.ssa_context_t.index = 0

    if self.disasm is None or self.disasm == 'ir-parser':
      dis = parser_disassembler(input)
      dis.stackreg = 'esp'
    elif self.disasm == 'capstone-x86':
      md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
      dis = host.dis.available_disassemblers['capstone'].create(md, input)
    elif self.disasm == 'capstone-x86-64':
      md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
      dis = host.dis.available_disassemblers['capstone'].create(md, input)
    dec = decompiler_t(dis, 0)

    dec.step_until(last_step)

    return dec

  def tokenize(self, flow):
    t = c.tokenizer(flow, indent='  ')
    tokens = list(t.flow_tokens())
    return self.unindent(''.join([str(t) for t in tokens]))

  def objdump_to_hex(self, input):
    hex = re.findall(r'^\s*[a-f0-9]*:((?:\s(?:[a-f0-9]{2}))*)', input, flags=re.MULTILINE)
    hex = ''.join(hex).replace(' ', '')
    return binascii.unhexlify(hex)

  def objdump_load(self, filename):
    filepath = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), filename))
    data = file(filepath, 'rb').read()
    parsed = re.findall(r'([a-f0-9]+) \<([^\>]+)\>\:\n((?:\s+[a-f0-9]+:(?:\s(?:[a-f0-9]{2}))*\s+[^\n]*)*\n)', data, flags=re.MULTILINE)
    Function = namedtuple('Point', ['address', 'name', 'text', 'hex'])
    functions = {o[1]: Function(address=int(o[0], 16),name=o[1],text=o[2],hex=self.objdump_to_hex(o[2])) for o in parsed}
    return functions

  def assert_step(self, step, input, expected):
    d = self.decompile_until(input, step)
    result = self.tokenize(d.flow)
    expected = self.unindent(expected)
    self.assertMultiLineEqual(expected, result)
    return
