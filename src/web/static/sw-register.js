// Service worker registration temporarily disabled for debugging.
// (ngrok free serves an interstitial HTML page that breaks fetch/JSON calls,
//  and the SW cache was masking updates. Re-enable once tunneling is stable.)
// if ("serviceWorker" in navigator && !window.Telegram?.WebApp) {
//   window.addEventListener("load", () => {
//     navigator.serviceWorker.register("/sw.js").catch(() => {});
//   });
// }
