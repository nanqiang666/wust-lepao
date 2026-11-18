# -*- coding: utf-8 -*-
"""反编译引用关键字符串的方法, 重点看 getCaptureStatus 调用与 stopRun 组装"""
import glob
import os
import struct

def uleb(buf, pos):
    r, s = 0, 0
    while True:
        b = buf[pos]; pos += 1
        r |= (b & 0x7f) << s
        if not (b & 0x80):
            return r, pos
        s += 7

INSN_LEN = [1]*256
for op in [0x02,0x05,0x08,0x13,0x15,0x16,0x19,0x1a,0x1c,0x1f,0x20,0x22,0x23,0x29,0x2d,0x2e,0x2f,0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0x3a,0x3b,0x3c,0x3d]+list(range(0x44,0x6e))+list(range(0xd0,0xe3)):
    INSN_LEN[op] = 2
for op in [0x03,0x06,0x09,0x14,0x17,0x1b,0x24,0x25,0x26,0x2a,0x2b,0x2c]+list(range(0x6e,0x79)):
    INSN_LEN[op] = 3
INSN_LEN[0x18] = 5

class Dex:
    def __init__(self, d):
        self.d = d
        self.str_ids_size, self.str_ids_off = struct.unpack_from("<II", d, 56)
        self.type_ids_size, self.type_ids_off = struct.unpack_from("<II", d, 64)
        self.proto_ids_size, self.proto_ids_off = struct.unpack_from("<II", d, 72)
        self.field_ids_size, self.field_ids_off = struct.unpack_from("<II", d, 80)
        self.method_ids_size, self.method_ids_off = struct.unpack_from("<II", d, 88)
        self.class_defs_size, self.class_defs_off = struct.unpack_from("<II", d, 96)
        self._str = {}
    def str(self, i):
        if i < 0 or i >= self.str_ids_size: return ""
        if i in self._str: return self._str[i]
        off = struct.unpack_from("<I", self.d, self.str_ids_off + i*4)[0]
        _, p = uleb(self.d, off)
        end = self.d.find(b"\x00", p)
        s = self.d[p:end].decode("utf-8", "replace")
        self._str[i] = s
        return s
    def type(self, i):
        if i < 0 or i >= self.type_ids_size: return "?"
        return self.str(struct.unpack_from("<I", self.d, self.type_ids_off + i*4)[0])
    def proto(self, idx):
        if idx < 0 or idx >= self.proto_ids_size: return "?", []
        try:
            _, r, po = struct.unpack_from("<III", self.d, self.proto_ids_off + idx*12)
        except struct.error:
            return "?", []
        p = []
        if po and po + 4 <= len(self.d):
            n = struct.unpack_from("<I", self.d, po)[0]
            for k in range(min(n, 64)):
                if po+4+k*2+2 > len(self.d): break
                p.append(self.type(struct.unpack_from("<H", self.d, po+4+k*2)[0]))
        return self.type(r), p
    def method(self, idx):
        c, p, n = struct.unpack_from("<HHI", self.d, self.method_ids_off + idx*8)
        r, params = self.proto(p)
        return f"{self.type(c)}->{self.str(n)}({','.join(params)}):{r}"
    def field(self, idx):
        c, t, n = struct.unpack_from("<HHI", self.d, self.field_ids_off + idx*8)
        return f"{self.type(c)}->{self.str(n)}:{self.type(t)}"

    def dump_method(self, coff, mname):
        d = self.d
        print(f"\n===== {mname} (@0x{coff:x}) =====")
        regs, ins, outs, tries, dbg, sz = struct.unpack_from("<HHHHII", d, coff)
        pos = coff + 16; end = pos + sz*2
        while pos < end:
            op = d[pos]; b1 = d[pos+1]; pc = (pos-(coff+16))//2
            if op == 0x00 and b1 != 0x00:
                break
            if op == 0x1a:
                print(f"  {pc:04x}: const-string v{b1}, {self.str(struct.unpack_from('<H', d, pos+2)[0])!r}")
            elif op == 0x1b:
                print(f"  {pc:04x}: const-string/jumbo v{b1}, {self.str(struct.unpack_from('<I', d, pos+2)[0])!r}")
            elif 0x60 <= op <= 0x66:
                print(f"  {pc:04x}: sget v{b1}, {self.field(struct.unpack_from('<H', d, pos+2)[0])}")
            elif 0x67 <= op <= 0x6d:
                print(f"  {pc:04x}: sput v{b1}, {self.field(struct.unpack_from('<H', d, pos+2)[0])}")
            elif 0x52 <= op <= 0x58:
                print(f"  {pc:04x}: iget v{b1&0xf}, v{b1>>4}, {self.field(struct.unpack_from('<H', d, pos+2)[0])}")
            elif 0x59 <= op <= 0x5f:
                print(f"  {pc:04x}: iput v{b1&0xf}, v{b1>>4}, {self.field(struct.unpack_from('<H', d, pos+2)[0])}")
            elif 0x6e <= op <= 0x72:
                mid = struct.unpack_from("<H", d, pos+2)[0]; rw = struct.unpack_from("<H", d, pos+4)[0]
                rl = [rw&0xf,(rw>>4)&0xf,(rw>>8)&0xf,(rw>>12)&0xf,b1&0xf][:b1>>4]
                kn = {0x6e:"virtual",0x6f:"super",0x70:"direct",0x71:"static",0x72:"iface"}[op]
                print(f"  {pc:04x}: invoke-{kn} {{{','.join('v'+str(r) for r in rl)}}}, {self.method(mid)}")
            elif 0x74 <= op <= 0x78:
                mid = struct.unpack_from("<H", d, pos+2)[0]; rc = struct.unpack_from("<H", d, pos+4)[0]
                print(f"  {pc:04x}: invoke-range {{v{rc}..v{rc+b1-1}}}, {self.method(mid)}")
            elif op == 0x22:
                print(f"  {pc:04x}: new-instance v{b1}, {self.type(struct.unpack_from('<H', d, pos+2)[0])}")
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
                off = struct.unpack_from("<h", d, pos+2)[0]
                cn = {0x32:"if-eq",0x33:"if-ne",0x34:"if-lt",0x35:"if-ge",0x36:"if-gt",0x37:"if-le"}[op]
                print(f"  {pc:04x}: {cn} v{b1&0xf}, v{b1>>4} -> {pc+off:04x}")
            elif 0x38 <= op <= 0x3d:
                off = struct.unpack_from("<h", d, pos+2)[0]
                cn = {0x38:"if-eqz",0x39:"if-nez",0x3a:"if-ltz",0x3b:"if-gez",0x3c:"if-gtz",0x3d:"if-lez"}[op]
                print(f"  {pc:04x}: {cn} v{b1} -> {pc+off:04x}")
            elif op == 0x28:
                off = struct.unpack_from("<b", d, pos+1)[0]
                print(f"  {pc:04x}: goto -> {pc+off:04x}")
            elif op == 0x29:
                off = struct.unpack_from("<h", d, pos+2)[0]
                print(f"  {pc:04x}: goto/16 -> {pc+off:04x}")
            pos += INSN_LEN[op]*2

TARGET_STRS = ["getCaptureStatus", "getCaptureStatus startTime", "getCaptureStatus usedTime",
               "getCaptureStatus userInfo", "stopRunService", "capture_num", "faceVerify"]

dex_dir = os.path.dirname(os.path.abspath(__file__))
# 找到引用目标字符串的方法并 dump
for fp in sorted(glob.glob(os.path.join(dex_dir, "classes*.dex"))):
    d = Dex(open(fp, "rb").read())
    # 收集目标 string index
    tgt_idx = set()
    for i in range(d.str_ids_size):
        s = d.str(i)
        if any(t in s for t in TARGET_STRS):
            tgt_idx.add(i)
    if not tgt_idx:
        continue
    print(f"\n########## {os.path.basename(fp)} (目标字符串 {len(tgt_idx)} 个) ##########")
    for ci in range(d.class_defs_size):
        c_idx, acc, sup, ifo, src, ann, cdo, svo = struct.unpack_from("<IIIIIIII", d.d, d.class_defs_off + ci*32)
        cname = d.type(c_idx)
        if not cdo:
            continue
        p = cdo
        sf, p = uleb(d.d, p); iff, p = uleb(d.d, p); dm, p = uleb(d.d, p); vm, p = uleb(d.d, p)
        for _ in range(sf + iff):
            _, p = uleb(d.d, p); _, p = uleb(d.d, p)
        midx = 0
        for mc in (dm, vm):
            for _ in range(mc):
                dmi, p = uleb(d.d, p); _, p = uleb(d.d, p); coff, p = uleb(d.d, p)
                midx += dmi
                if not coff:
                    continue
                mname = d.method(midx)
                # 方法名本身包含关键名就 dump
                if any(k in mname for k in ("getCaptureStatus", "stopRun", "faceVerify", "capture")):
                    d.dump_method(coff, f"[{cname}] {mname}")
