// CloudFront Function (viewer request): send client-side routes like /p/01J... to index.html.
// Requests for real files (anything with an extension) and /api/* pass through untouched.
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri.startsWith("/api/")) {
    return request;
  }
  var last = uri.substring(uri.lastIndexOf("/") + 1);
  if (last.indexOf(".") === -1) {
    request.uri = "/index.html";
  }
  return request;
}
