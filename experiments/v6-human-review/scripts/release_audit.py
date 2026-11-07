"""Read-only ClipSift repository release audit. No publishing, no file copying."""
from __future__ import annotations
import ast, json, os, re, subprocess, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.venv','.git','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','node_modules','outputs','.idea','.vscode','.backup','backup','backups','clipsift_github_handoff'}
SENSITIVE_DIRS = {'models','data'}
BLOCK_SUFFIX = {'.mp4','.mov','.avi','.mkv','.webm','.pth','.pt','.onnx','.ckpt','.safetensors','.pkl','.pickle','.env','.pem','.key','.p12','.pfx','.sqlite','.db','.zip','.7z','.rar'}
PUBLIC_SUFFIX = {'.py','.html','.css','.js','.ts','.tsx','.json','.md','.txt','.yml','.yaml','.toml','.csv','.ps1','.gitignore'}
WARN_PATTERNS = [
 ('windows_absolute_path',re.compile(r'[A-Za-z]:\\(?:Users|SMU|Desktop|Documents|Downloads)\\',re.I)),
 ('localhost_dependency',re.compile(r'http://(?:localhost|127\.0\.0\.1):\d+',re.I)),
 ('potential_key_assignment',re.compile(r'(?im)^\s*(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)\s*[:=]\s*[\"\']?[^\s\"\']{8,}')),
]

def git(*args):
    try:
        p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,text=True,timeout=6)
        return p.stdout.strip() if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired): return None

def audit():
    files=[]; risks=[]; counts=Counter(); py_errors=[]; top=[]
    for p in sorted(ROOT.iterdir()): top.append(p.name)
    for dp, dirs, filenames in os.walk(ROOT):
        base=Path(dp); dirs[:]=sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith('.bak'))
        for name in sorted(filenames):
            p=base/name; rel=p.relative_to(ROOT).as_posix(); suffix=p.suffix.lower(); counts[rel.split('/')[0]]+=1
            try: size=p.stat().st_size
            except OSError: continue
            reasons=[]
            if suffix in BLOCK_SUFFIX: reasons.append('restricted_extension')
            if size>10*1024*1024: reasons.append('over_10MiB')
            if rel.split('/')[0] in SENSITIVE_DIRS: reasons.append('review_data_or_model_permissions')
            if re.search(r'(?i)(?:^|/)(?:\.env[^/]*|.*(?:token|secret|credential|password|private)[^/]*)$',rel): reasons.append('sensitive_filename')
            if re.search(r'(?i)(?:\.bak\b|backup|_old\.|\(\d+\)\.)',rel): reasons.append('backup_or_duplicate')
            if suffix=='.py':
                try: ast.parse(p.read_text(encoding='utf-8-sig'),filename=rel)
                except (SyntaxError,UnicodeError) as e: py_errors.append({'path':rel,'error':str(e)[:200]})
            if size<=750000 and suffix in PUBLIC_SUFFIX and suffix not in {'.csv'}:
                try:
                    content=p.read_text(encoding='utf-8-sig')
                    for label,pattern in WARN_PATTERNS:
                        if pattern.search(content): reasons.append(label)
                except (UnicodeError,OSError): pass
            record={'path':rel,'size_bytes':size,'risk_flags':sorted(set(reasons))}
            files.append(record)
            if reasons: risks.append(record)
    routes={route:(ROOT/'app'/file).exists() for route,file in [('videos','videos.html'),('subsamples','subsamples.html'),('review','review.html'),('results','results.html')]}
    return {
      'created_utc':datetime.now(timezone.utc).isoformat(),
      'root':str(ROOT), 'is_git_repo':git('rev-parse','--is-inside-work-tree')=='true',
      'git_branch':git('branch','--show-current'), 'git_remote':git('remote','-v'),
      'top_level':top, 'files_count':len(files), 'counts_by_top_level':dict(counts),
      'html_page_exists':routes, 'python_syntax_errors':py_errors,
      'flagged_paths':risks,
      'recommendations':[
        'Do not push before the group repo is accessible and contents have been compared.',
        'Do not git add .; review each staged file and confirm gitignore.',
        'Never commit video, model weights, private data, local output, .venv, or secrets.',
        'The audit lists potential problems; it does not guarantee security or deployability.',
      ],
    }

def main():
    result=audit(); out=ROOT/'outputs'/'release_audit'; out.mkdir(parents=True,exist_ok=True)
    j=out/'release_audit.json'; j.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# ClipSift release audit','',f"Git initialized: **{result['is_git_repo']}**",f"Total inspected files: **{result['files_count']}**",f"Flagged paths: **{len(result['flagged_paths'])}**",f"Python syntax issues: **{len(result['python_syntax_errors'])}**",'', '## Page files (name check, not functional test)', '']
    lines += [f"- {name}: {'found' if ok else 'not found under app/'}" for name,ok in result['html_page_exists'].items()]
    lines += ['','## Files needing manual review','']
    lines += [f"- `{r['path']}`: {', '.join(r['risk_flags'])}" for r in result['flagged_paths'][:150]] or ['- None flagged by automated checks']
    lines += ['','## Syntax issues','']
    lines += [f"- `{r['path']}`: {r['error']}" for r in result['python_syntax_errors'][:30]] or ['- None found']
    lines += ['','## Release gate','', 'Only prepare a PR after group access is granted, repo structures are compared, and flagged files are reviewed.']
    m=out/'release_audit.md';m.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Release audit (READ ONLY for source files)')
    print('Files inspected:',result['files_count'])
    print('Flagged paths:',len(result['flagged_paths']))
    print('Python syntax issues:',len(result['python_syntax_errors']))
    print('Git repo:',result['is_git_repo'])
    print('Report:',m)
    print('JSON:',j)
    print('NOTE: Review reports before sharing; filenames may be sensitive.')
if __name__=='__main__': main()
