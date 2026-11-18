# -*- coding: utf-8 -*-
import glob
import os
import struct
import sys

def uleb128(buf, pos):
    res, shift = 0, 0
    while True:
        b = buf[pos]; pos += 1
        res |= (b & 0x7f) << shift
        if not (b & 0x80):
            return res, pos
        shift += 7

INSN_LEN = [1]*256
for op in [0x02,0x05,0x08,0x13,0x15,0x16,0x19,0x1a,0x1c,0x1f,0x20,0x22,0x23,0x29,0x2d,0x2e,0x2f,0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0x3a,0x3b,0x3c,0x3d] + list(range(0x44,0x6e)) + list(range(0xd0,0xe3)):
    INSN_LEN[op] = 2
for op in [0x03,0x06,0x09,0x14,0x17,0x1b,0x24,0x25,0x26,0x2a,0x2b,0x2c] + list(range(0x6e,0x79)):
    INSN_LEN[op] = 3
INSN_LEN[0x18] = 5

class DexFile:
    def __init__(self, path):
        self.dex = open(path, "rb").read()
        d = self.dex
        self.string_ids_size, self.string_ids_off = struct.unpack_from("<II", d, 56)
        self.type_ids_size, self.type_ids_off = struct.unpack_from("<II", d, 64)
        self.proto_ids_size, self.proto_ids_off = struct.unpack_from("<II", d, 72)
        self.field_ids_size, self.field_ids_off = struct.unpack_from("<II", d, 80)
        self.method_ids_size, self.method_ids_off = struct.unpack_from("<II", d, 88)
        self.class_defs_size, self.class_defs_off = struct.unpack_from("<II", d, 96)
        self._strs = {}

    def get_str(self, i):
        if i < 0 or i >= self.string_ids_size: return ""
        if i in self._strs: return self._strs[i]
        soff = struct.unpack_from("<I", self.dex, self.string_ids_off + i * 4)[0]
        _, p = uleb128(self.dex, soff)
        end = self.dex.find(b"\x00", p)
        s = self.dex[p:end].decode("utf-8", "replace")
        self._strs[i] = s
        return s

    def get_type(self, i):
        if i < 0 or i >= self.type_ids_size: return ""
        return self.get_str(struct.unpack_from("<I", self.dex, self.type_ids_off + i * 4)[0])

    def get_proto(self, idx):
        _, ret_idx, params_off = struct.unpack_from("<III", self.dex, self.proto_ids_off + idx * 12)
        params = []
        if params_off:
            sz = struct.unpack_from("<I", self.dex, params_off)[0]
            for i in range(sz):
                params.append(self.get_type(struct.unpack_from("<H", self.dex, params_off + 4 + i * 2)[0]))
        return self.get_type(ret_idx), params

    def get_method(self, idx):
        c_idx, p_idx, n_idx = struct.unpack_from("<HHI", self.dex, self.method_ids_off + idx * 8)
        ret, params = self.get_proto(p_idx)
        return f"{self.get_type(c_idx)}->{self.get_str(n_idx)}({','.join(params)}):{ret}"

    def get_field(self, idx):
        c_idx, t_idx, n_idx = struct.unpack_from("<HHI", self.dex, self.field_ids_off + idx * 8)
        return f"{self.get_type(c_idx)}->{self.get_str(n_idx)}:{self.get_type(t_idx)}"

    def dump_code(self, coff, title=""):
        d = self.dex
        print(f"\n=== {title} (@0x{coff:x}) ===")
        if not coff:
            print("  <abstract/native>")
            return
        regs, ins, outs, tries, dbg, insns_sz = struct.unpack_from("<HHHHII", d, coff)
        print(f"  [regs={regs} ins={ins} outs={outs} insns={insns_sz}]")
        pos = coff + 16; end = pos + insns_sz * 2
        while pos < end:
            op = d[pos]; b1 = d[pos+1]; pc = (pos - (coff + 16)) // 2
            if op == 0x00 and b1 != 0x00:
                break
            w = INSN_LEN[op] * 2
            if op == 0x1a:
                print(f"  {pc:04x}: const-string v{b1}, {self.get_str(struct.unpack_from('<H', d, pos+2)[0])!r}")
            elif op == 0x1b:
                print(f"  {pc:04x}: const-string/jumbo v{b1}, {self.get_str(struct.unpack_from('<I', d, pos+2)[0])!r}")
            elif 0x60 <= op <= 0x66:
                print(f"  {pc:04x}: sget v{b1}, {self.get_field(struct.unpack_from('<H', d, pos+2)[0])}")
            elif 0x67 <= op <= 0x6d:
                print(f"  {pc:04x}: sput v{b1}, {self.get_field(struct.unpack_from('<H', d, pos+2)[0])}")
            elif 0x52 <= op <= 0x58:
                print(f"  {pc:04x}: iget v{b1&0xf}, v{b1>>4}, {self.get_field(struct.unpack_from('<H', d, pos+2)[0])}")
            elif 0x59 <= op <= 0x5f:
                print(f"  {pc:04x}: iput v{b1&0xf}, v{b1>>4}, {self.get_field(struct.unpack_from('<H', d, pos+2)[0])}")
            elif 0x6e <= op <= 0x72:
                mid = struct.unpack_from("<H", d, pos+2)[0]; rw = struct.unpack_from("<H", d, pos+4)[0]
                rlist = [rw&0xf,(rw>>4)&0xf,(rw>>8)&0xf,(rw>>12)&0xf,b1&0xf][:b1>>4]
                kname = {0x6e:"virtual",0x6f:"super",0x70:"direct",0x71:"static",0x72:"iface"}[op]
                rstr = ",".join("v" + str(r) for r in rlist)
                print(f"  {pc:04x}: invoke-{kname} {{{rstr}}}, {self.get_method(mid)}")
            elif 0x74 <= op <= 0x78:
                mid = struct.unpack_from("<H", d, pos+2)[0]; rc = struct.unpack_from("<H", d, pos+4)[0]
                print(f"  {pc:04x}: invoke-range {{v{rc}..v{rc+b1-1}}}, {self.get_method(mid)}")
            elif op == 0x22:
                print(f"  {pc:04x}: new-instance v{b1}, {self.get_type(struct.unpack_from('<H', d, pos+2)[0])}")
            elif op == 0x12:
                val = b1>>4; val = val-16 if val>=8 else val
                print(f"  {pc:04x}: const/4 v{b1&0xf}, {val}")
            elif op == 0x13:
                print(f"  {pc:04x}: const/16 v{b1}, {struct.unpack_from('<h', d, pos+2)[0]}")
            elif op == 0x14:
                print(f"  {pc:04x}: const v{b1}, {struct.unpack_from('<i', d, pos+2)[0]}")
            elif op in (0x01,0x04,0x07):
                print(f"  {pc:04x}: move v{b1&0xf}, v{b1>>4}")
            elif op in (0x0a,0x0b,0x0c):
                print(f"  {pc:04x}: move-result v{b1}")
            elif op in (0x0e,0x0f,0x10,0x11):
                print(f"  {pc:04x}: return v{b1}")
            elif 0x32 <= op <= 0x37:
                off16 = struct.unpack_from("<h", d, pos+2)[0]
                cname = {0x32:"if-eq",0x33:"if-ne",0x34:"if-lt",0x35:"if-ge",0x36:"if-gt",0x37:"if-le"}[op]
                print(f"  {pc:04x}: {cname} v{b1&0xf}, v{b1>>4} -> {pc+off16:04x}")
            elif 0x38 <= op <= 0x3d:
                off16 = struct.unpack_from("<h", d, pos+2)[0]
                cname = {0x38:"if-eqz",0x39:"if-nez",0x3a:"if-ltz",0x3b:"if-gez",0x3c:"if-gtz",0x3d:"if-lez"}[op]
                print(f"  {pc:04x}: {cname} v{b1} -> {pc+off16:04x}")
            elif op == 0x28:
                off8 = struct.unpack_from("<b", d, pos+1)[0]
                print(f"  {pc:04x}: goto -> {pc+off8:04x}")
            elif op == 0x29:
                off16 = struct.unpack_from("<h", d, pos+2)[0]
                print(f"  {pc:04x}: goto/16 -> {pc+off16:04x}")
            pos += w

    def dump_class(self, target_cname, method_filter=None):
        d = self.dex
        for ci in range(self.class_defs_size):
            c_idx, acc, sup_idx, if_off, src_idx, ann_off, cdata_off, svals_off = struct.unpack_from("<IIIIIIII", d, self.class_defs_off + ci * 32)
            cname = self.get_type(c_idx)
            if cname == target_cname:
                print(f"*** Class {cname} (sup={self.get_type(sup_idx)}) ***")
                if not cdata_off: return
                p = cdata_off
                sf, p = uleb128(d, p); if_f, p = uleb128(d, p); dm, p = uleb128(d, p); vm, p = uleb128(d, p)
                for _ in range(sf + if_f): _, p = uleb128(d, p); _, p = uleb128(d, p)
                for mc in (dm, vm):
                    midx = 0
                    for _ in range(mc):
                        dmi, p = uleb128(d, p); _, p = uleb128(d, p); coff, p = uleb128(d, p); midx += dmi
                        mname = self.get_method(midx)
                        if not method_filter or method_filter in mname:
                            self.dump_code(coff, mname)

if __name__ == "__main__":
    dex_dir = os.path.dirname(os.path.abspath(__file__))
    for spec in sys.argv[1:]:
        if ":" in spec:
            cls, mf = spec.split(":", 1)
        else:
            cls, mf = spec, None
        for fp in sorted(glob.glob(os.path.join(dex_dir, "classes*.dex"))):
            DexFile(fp).dump_class(cls, mf)
