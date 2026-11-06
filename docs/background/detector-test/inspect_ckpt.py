import zipfile,pickletools,sys,glob,collections
for f in sorted(glob.glob('weights/*.pth')):
    z=zipfile.ZipFile(f); n=[x for x in z.namelist() if x.endswith('data.pkl')][0]
    g=collections.Counter(); strs=[]
    for op,arg,pos in pickletools.genops(z.read(n)):
        if op.name in('SHORT_BINUNICODE','BINUNICODE') and isinstance(arg,str): strs.append(arg)
        if op.name=='GLOBAL': g[arg.replace(' ','.')]+=1
        if op.name=='STACK_GLOBAL' and len(strs)>=2: g[strs[-2]+'.'+strs[-1]]+=1
    bad=[k for k in g if k.split('.')[0] in('os','subprocess','sys','builtins','posix','socket','shutil','importlib','runpy','eval','exec','pty','requests','urllib')]
    print(f[8:40],len(g),'suspicious:',bad); print('  ',sorted(g)[:14])
