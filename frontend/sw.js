self.addEventListener('push', event => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'Novo pedido!', body: event.data ? event.data.text() : '' };
  }

  event.waitUntil(
    self.registration.showNotification(data.title || 'Novo pedido!', {
      body: data.body || '',
      tag: data.tag || 'pedido',
    })
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
      for (const client of clientList) {
        if (client.url.includes('estabelecimento.html') && 'focus' in client) {
          return client.focus();
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow('/html/estabelecimento.html');
      }
    })
  );
});
