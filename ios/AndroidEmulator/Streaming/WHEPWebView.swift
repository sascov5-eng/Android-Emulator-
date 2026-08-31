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
        loadPlayer(in: webView, coordinator: context.coordinator)
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        if context.coordinator.loadedURL != whepURL {
            loadPlayer(in: webView, coordinator: context.coordinator)
        }
    }

    private func loadPlayer(in webView: WKWebView, coordinator: Coordinator) {
        coordinator.loadedURL = whepURL
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
            let stopped = false;
            let retryCount = 0;
            const maxRetries = 8;

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

            async function disposePeer() {
              const oldResource = resourceURL;
              resourceURL = null;
              if (pc) {
                pc.onconnectionstatechange = null;
                pc.ontrack = null;
                pc.close();
                pc = null;
              }
              if (oldResource) {
                try { await fetch(oldResource, { method: 'DELETE' }); } catch (_) {}
              }
            }

            async function connect() {
              if (stopped) return;
              await disposePeer();

              const peer = new RTCPeerConnection();
              pc = peer;
              peer.addTransceiver('video', { direction: 'recvonly' });
              peer.ontrack = event => {
                retryCount = 0;
                if (event.streams && event.streams[0]) {
                  video.srcObject = event.streams[0];
                } else {
                  video.srcObject = new MediaStream([event.track]);
                }
                video.play().catch(() => {});
              };
              peer.onconnectionstatechange = () => {
                if (stopped || peer !== pc) return;
                if (peer.connectionState === 'failed' || peer.connectionState === 'disconnected') {
                  scheduleReconnect();
                }
              };

              const offer = await peer.createOffer();
              await peer.setLocalDescription(offer);
              await waitForIceGatheringComplete(peer);

              const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/sdp' },
                body: peer.localDescription.sdp
              });
              if (!response.ok) throw new Error('WHEP HTTP ' + response.status);

              const location = response.headers.get('Location');
              if (location) resourceURL = new URL(location, endpoint).toString();
              const answer = await response.text();
              await peer.setRemoteDescription({ type: 'answer', sdp: answer });
            }

            function scheduleReconnect() {
              if (stopped || retryCount >= maxRetries) return;
              const delay = Math.min(1000 * Math.pow(2, retryCount), 8000);
              retryCount += 1;
              setTimeout(() => {
                if (!stopped) connect().catch(scheduleReconnect);
              }, delay);
            }

            async function stop() {
              stopped = true;
              await disposePeer();
            }

            window.addEventListener('pagehide', stop);
            connect().catch(scheduleReconnect);
          })();
          </script>
        </body>
        </html>
        """
        webView.loadHTMLString(html, baseURL: nil)
    }

    private static func javascriptString(_ value: String) -> String {
        let data = try! JSONSerialization.data(withJSONObject: [value])
        let array = String(data: data, encoding: .utf8)!
        return String(array.dropFirst().dropLast())
    }

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate {
        var loadedURL: URL?

        func webView(
            _ webView: WKWebView,
            decidePolicyFor navigationAction: WKNavigationAction
        ) async -> WKNavigationActionPolicy {
            let url = navigationAction.request.url
            let isLocalDocument = url == nil || url?.scheme == "about"
            return isLocalDocument ? .allow : .cancel
        }
    }
}
