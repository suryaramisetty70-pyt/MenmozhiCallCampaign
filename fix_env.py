import os
with open('.env', 'rb') as f:
    data = f.read()

data_str = data.decode('utf-16le', errors='ignore') if b'\x00' in data else data.decode('utf-8', errors='ignore')
data_str = data_str.replace('\x00', '')

with open('.env', 'w', encoding='utf-8') as f:
    f.write(data_str)
