import SwiftUI
import WebKit

struct WHEPWebView: UIViewRepresentable {
    let whepURL: URL

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.isOpaque = false
        webView.backgroundColor = .black
        webView.scrollView.isScrollEnabled = false
        webView.scrollView.bounces = false
        loadPlayer(in: webView)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        if context.coordinator.loadedURL != whepURL {
            loadPlayer(in: webView)
        }
    }

    private func loadPlayer(in webView: WKWebView) {
        let urlLiteral = Self.javascriptString(whepURL.absoluteString)
        let html = """
        <!doctype html>
        <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
          <style>
            html, body { margin: 0; width: 100%; height: 100%; overflow: hidden; background: #000; }
            video { width: 100%; height: 100%; object-fit: contain; background: #000; }
          </style>
        </head>
        <body>
          <video id="video" autoplay playsinline muted></video>
          <script>
          (() => {
            const endpoint = \(urlLiteral);
            const video = document.getElementById('video');
            let pc = null;
            let resourceURL = null;

            function waitForIceGatheringComplete(peer) {
              if (peer.iceGatheringState === 'complete') return Promise.resolve();
              return new Promise(resolve => {
                const listener = () => {
                  if (peer.iceGatheringState === 'complete') {
                    peer.removeEventListener('icegatheringstatechange', listener);
                    resolve();
                  }
                };
                peer.addEventListener('icegatheringstatechange', listener);
              });
            }

            async function start() {
              pc = new RTCPeerConnection();
              pc.addTransceiver('video', { direction: 'recvonly' });
              pc.ontrack = event => {
                if (event.streams && event.streams[0]) {
                  video.srcObject = event.streams[0];
                } else {
                  const stream = new MediaStream([event.track]);
                  video.srcObject = stream;
                }
                video.play().catch(() => {});
              };

              const offer = await pc.createOffer();
              await pc.setLocalDescription(offer);
              await waitForIceGatheringComplete(pc);

              const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/sdp' },
                body: pc.localDescription.sdp
              });
              if (!response.ok) throw new Error('WHEP HTTP ' + response.status);

              const location = response.headers.get('Location');
              if (location) resourceURL = new URL(location, endpoint).toString();
              const answer = await response.text();
              await pc.setRemoteDescription({ type: 'answer', sdp: answer });
            }

            async function stop() {
              if (resourceURL) {
                try { await fetch(resourceURL, { method: 'DELETE' }); } catch (_) {}
              }
              if (pc) pc.close();
            }

            window.addEventListener('pagehide', stop);
            start().catch(error => {
              document.body.dataset.error = error.message || 'stream failed';
            });
          })();
          </script>
        </body>
        </html>
        """
        webView.navigationDelegate = webView.navigationDelegate
        webView.loadHTMLString(html, baseURL: nil)
    }

    private static func javascriptString(_ value: String) -> String {
        let data = try! JSONSerialization.data(withJSONObject: [value])
        let array = String(data: data, encoding: .utf8)!
        return String(array.dropFirst().dropLast())
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var loadedURL: URL?

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction,
            decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
        ) {
            if navigationAction.navigationType == .other,
               navigationAction.request.url?.scheme == "about" || navigationAction.request.url == nil {
                decisionHandler(.allow)
            } else {
                decisionHandler(.cancel)
            }
        }
    }
}
