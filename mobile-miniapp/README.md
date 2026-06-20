# PenMoji Mobile Capture

WeChat Mini Program front-end for quick PenMoji inspiration capture.

Purpose:

- Capture ideas, links, comment observations, quotes, and material leads on mobile.
- Keep failed submissions in a local retry queue so ideas are not lost.
- Send each item to the cloud queue with tags and a desktop-side processing intent.
- Check whether the desktop workbench has received or archived the item.

Default local sync service:

```text
http://127.0.0.1:8787
```

In WeChat DevTools, import this folder as a mini-program project. For local development, enable the DevTools option that skips domain validation, or replace the sync base URL with a deployed HTTPS endpoint.

The mini-program intentionally keeps production work on the desktop workbench. Mobile is for capture, tagging, retry, and sync visibility.
