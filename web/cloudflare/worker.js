import media from './media-manifest.json';
import { serveMedia } from './media-handler.js';

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (Object.hasOwn(media, path)) {
      return serveMedia(request, env.MEDIA, media[path]);
    }
    return env.ASSETS.fetch(request);
  },
};
