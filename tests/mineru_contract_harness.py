"""QA reference driver, NOT a production MinerU implementation.

Fix must run the same scenarios against its real client before acceptance.
All network in this harness requires an explicit httpx.MockTransport.
"""
import io
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote, urlsplit
import httpx


class ContractDriver:
    def __init__(self, transport, base='https://api.invalid/proxy', key='synthetic-key'):
        if not isinstance(transport, httpx.MockTransport):
            raise ValueError('MockTransport required')
        self.base, self.key = base.rstrip('/'), key
        self.http = httpx.Client(transport=transport, follow_redirects=False, timeout=2)

    def request(self, method, url, **kwargs):
        headers = dict(kwargs.pop('headers', {}))
        if urlsplit(url)[:2] == urlsplit(self.base)[:2]:
            headers.setdefault('Authorization', 'Bearer ' + self.key)
        for _ in range(4):
            response = self.http.request(method, url, headers=headers, **kwargs)
            if response.status_code not in (301,302,303,307,308):
                response.raise_for_status()
                return response
            url = str(response.url.join(response.headers['location']))
            headers = {k:v for k,v in headers.items() if k.lower() != 'authorization'}
        raise ValueError('redirect limit')

    def create(self, files):
        # POST 不自动重试：超时时无法确定服务端是否已提交。
        return self.request('POST', self.base+'/v1/tasks', json={
            'files': files, 'tier':'standard', 'output_formats':['default']}).json()

    def poll(self, task_id, max_polls=3, interval=0, sleep=lambda _: None):
        for _ in range(max_polls):
            result = self.request('GET', self.base+'/v1/tasks/'+quote(task_id,safe='')).json()
            if result['status'] in {'completed','partial','failed','canceled'}:
                return result
            sleep(interval)
        raise TimeoutError(task_id)

    def upload(self, file, content):
        if file['status']=='waiting-file' and 'upload' in file:
            target = file['upload']
            self.request('PUT', target['url'], headers=target['headers'], content=content)

    def download(self, file):
        payload = self.request('GET', file['result_url']).content
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            if archive.testzip() is not None:
                raise ValueError('corrupt member')
            for name in archive.namelist():
                path = PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                    raise ValueError('unsafe archive path')
            if not any(n.endswith('.md') for n in archive.namelist()):
                raise ValueError('missing markdown')
            return archive.namelist()
