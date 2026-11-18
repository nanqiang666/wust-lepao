# -*- coding: utf-8 -*-
"""在 dex 中定位引用关键抓拍/人脸字符串的类与方法"""
import glob
import os
import struct
import sys

def uleb(buf, pos):
    r, s = 0, 0
    while True:
        b = buf[pos]; pos += 1
        r |= (b & 0x7f) << s
        if not (b & 0x80):
            return r, pos
        s += 7

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
        return self.str(struct.unpack_from("<I", self.d, self.type_ids_off + i*4)[0]) if 0 <= i < self.type_ids_size else ""
    def proto(self, idx):
        _, r, po = struct.unpack_from("<III", self.d, self.proto_ids_off + idx*12)
        p = []
        if po:
            n = struct.unpack_from("<I", self.d, po)[0]
            for k in range(n):
                p.append(self.type(struct.unpack_from("<H", self.d, po+4+k*2)[0]))
        return self.type(r), p
    def method(self, idx):
        c, p, n = struct.unpack_from("<HHI", self.d, self.method_ids_off + idx*8)
        r, params = self.proto(p)
        return f"{self.type(c)}->{self.str(n)}({','.join(params)}):{r}"

TARGETS = ["start_face_verify", "face_verify_id", "capture_num", "middle_face_verify",
           "getCaptureStatus", "stop_face_verify", "run_face_verify_id", "is_capture_zone",
           "day_capture_num", "capture_type", "faceVerify", "ossCallback", "capturePhoto",
           "capture_num=", "face_auth_status", "face_verify_status"]

# 先收集所有 dex 里含目标字符串的 string index
for fp in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "classes*.dex"))):
    d = Dex(open(fp, "rb").read())
    hits = {}
    for i in range(d.str_ids_size):
        s = d.str(i)
        for t in TARGETS:
            if t in s:
                hits.setdefault(t, []).append((i, s))
    if not hits:
        continue
    print(f"\n########## {os.path.basename(fp)} ##########")
    # 遍历 class_defs，找 method 的 code 里引用了这些 string index
    str_idx_set = set(i for v in hits.values() for i, _ in v)
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
                # 检查 code 里是否引用目标 string
                regs, ins, outs, tries, dbg, sz = struct.unpack_from("<HHHHII", d.d, coff)
                # 快速扫描 code 里的 string index 引用
                pos = coff + 16; end = pos + sz*2
                refd = set()
                while pos < end:
                    op = d.d[pos]; b1 = d.d[pos+1]
                    if op == 0x00 and b1 != 0x00:
                        break
                    if op == 0x1a:
                        refd.add(struct.unpack_from("<H", d.d, pos+2)[0])
                        pos += 4
                    elif op == 0x1b:
                        refd.add(struct.unpack_from("<I", d.d, pos+2)[0])
                        pos += 6
                    else:
                        l = [1]*256
                        for o in [0x02,0x05,0x08,0x13,0x15,0x16,0x19,0x1a,0x1c,0x1f,0x20,0x22,0x23,0x29,0x2d,0x2e,0x2f,0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0x3a,0x3b,0x3c,0x3d]+list(range(0x44,0x6e))+list(range(0xd0,0xe3)):
                            l[o]=2
                        for o in [0x03,0x06,0x09,0x14,0x17,0x1b,0x24,0x25,0x26,0x2a,0x2b,0x2c]+list(range(0x6e,0x79)):
                            l[o]=3
                        l[0x18]=5
                        pos += l[op]*2
                inter = refd & str_idx_set
                if inter:
                    for si in inter:
                        s = d.str(si)
                        print(f"  [{cname}] {mname}")
                        print(f"      str#{si} = {s!r}")
