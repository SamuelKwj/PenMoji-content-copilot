# Mosmori Mobile Capture

Minimal WeChat Mini Program front-end for Mosmori mobile inspiration capture.

Purpose:

- Capture inspiration on mobile.
- Submit it to the local sync queue.
- Check sync status.

Default local sync service:

```text
http://127.0.0.1:8787
```

In WeChat DevTools, import this folder as a mini-program project. For local development, enable the DevTools option that skips domain validation, or replace the sync base URL with a deployed HTTPS endpoint.

This mini-program intentionally keeps the heavy workflow on the desktop Mosmori workbench.
