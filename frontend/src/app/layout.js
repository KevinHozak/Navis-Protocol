import "./globals.css";

export const metadata = {
  title: "Navis Protocol",
  description: "High-fidelity command bridge",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <title>Navis Protocol</title>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if (window.__TAURI_INTERNALS__) {
                // The desktop bundle owns its assets. A browser service worker
                // can retain an obsolete static export between executable builds.
                navigator.serviceWorker?.getRegistrations().then(function(registrations) {
                  registrations.forEach(function(registration) { registration.unregister(); });
                });
              } else
              if ('serviceWorker' in navigator) {
                if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                  navigator.serviceWorker.getRegistrations().then(function(registrations) {
                    let unregisteredAny = false;
                    let promises = [];
                    for (let registration of registrations) {
                      promises.push(
                        registration.unregister().then(function(success) {
                          if (success) {
                            console.log('Unregistered active service worker for local development');
                            unregisteredAny = true;
                          }
                        })
                      );
                    }
                    Promise.all(promises).then(function() {
                      if (unregisteredAny) {
                        if ('caches' in window) {
                          caches.keys().then(function(names) {
                            Promise.all(names.map(function(name) { return caches.delete(name); })).then(function() {
                              window.location.reload();
                            });
                          }).catch(function() {
                            window.location.reload();
                          });
                        } else {
                          window.location.reload();
                        }
                      }
                    });
                  });
                } else {
                  window.addEventListener('load', function() {
                    navigator.serviceWorker.register('/sw.js').then(
                      function(registration) {
                        console.log('ServiceWorker registration successful with scope: ', registration.scope);
                      },
                      function(err) {
                        console.log('ServiceWorker registration failed: ', err);
                      }
                    );
                  });
                }
              }
            `,
          }}
        />
      </head>
      <body style={{ backgroundColor: '#050505', color: '#f0f0f0' }}>{children}</body>
    </html>
  );
}
