export default {
  
    async fetch(request, env) {
    const url = new URL(request.url);
    const pathname = url.pathname.replace(/\/+$/, '');

  // DEBUG endpoint
  if (pathname === '/debug') {
    try {
      const list = await env.DATASETS.list({ limit: 10 });
      const debug = {
        binding_exists: !!env.DATASETS,
        list_result: list,
        object_count: list.objects?.length || 0,
        objects: list.objects?.map(o => o.key) || []
      };
      return new Response(JSON.stringify(debug, null, 2), {
        headers: { 'content-type': 'application/json' }
      });
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }, null, 2), {
        status: 500,
        headers: { 'content-type': 'application/json' }
      });
    }
  }

    // route: /datasets -> listing
    if (pathname === '/datasets') {
      // list objects in the bound R2 bucket (binding name: DATASETS)
      const list = await env.DATASETS.list({ limit: 1000 });
      const objects = list.objects || [];

      const rows = objects.map(o => {
        // encode key for URL path
        const encoded = encodeURIComponent(o.key);
        return `<li><a href="/datasets/${encoded}">${o.key}</a> (${o.size} bytes)</li>`;
      }).join('\n');

      const html = `<!doctype html>

      <html><head><meta charset="utf-8"><title>Datasets</title></head>
<body>
<h1>Datasets</h1>
<ul>${rows}</ul>
</body></html>`;

      return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8' } });
    }

    // route: /datasets/<key> -> serve object
    if (pathname.startsWith('/datasets/')) {
      const key = decodeURIComponent(pathname.slice('/datasets/'.length));
      const obj = await env.DATASETS.get(key);

      if (!obj) return new Response('Not found', { status: 404 });

      // propagate content-type if set, else fallback
      const headers = new Headers();
      const ct = obj.httpMetadata && obj.httpMetadata.contentType || obj.customMetadata && obj.customMetadata.contentType || 'application/octet-stream';
      headers.set('content-type', ct);
      // set content-disposition to prompt download if desired:
      // headers.set('content-disposition', `attachment; filename="${key.split('/').pop()}"`);

      return new Response(obj.body, { headers });
    }

    // fallback
    return new Response('Not Found', { status: 404 });
  }
}
