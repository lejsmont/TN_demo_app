function post(path, params) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = path;
  Object.keys(params).forEach((key) => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = key;
    input.value = params[key];
    form.appendChild(input);
  });
  document.body.appendChild(form);
  form.submit();
  document.body.removeChild(form);
}

function proceedAfterFingerprint(fingerprintStatus, state, postUrl) {
  const params = {
    state: state,
    fingerprintStatus: fingerprintStatus,
    challengeWindowSize: "05",
    browserAcceptHeader: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    browserColorDepth: window.screen.colorDepth,
    browserJavaEnabled: navigator.javaEnabled ? navigator.javaEnabled() : false,
    browserLanguage: navigator.language,
    browserScreenHeight: window.screen.height,
    browserScreenWidth: window.screen.width,
    browserTZ: new Date().getTimezoneOffset(),
    browserUserAgent: window.navigator.userAgent,
  };
  post(postUrl, params);
}

function doFingerprint(threeDsMethodUrl, threeDSMethodNotificationURL, threeDSMethodData, threeDSServerTransID, state, postUrl) {
  let done = false;
  const finish = (status) => {
    if (done) return;
    done = true;
    proceedAfterFingerprint(status, state, postUrl);
  };

  if (!threeDsMethodUrl) {
    finish("unavailable");
    return;
  }

  const html = `<script>
      document.addEventListener("DOMContentLoaded", function () {
        var form = document.createElement("form");
        form.method = "POST";
        form.action = "${threeDsMethodUrl}";
        form.appendChild(createInput("threeDSMethodNotificationURL", "${threeDSMethodNotificationURL}"));
        form.appendChild(createInput("threeDSMethodData", "${threeDSMethodData}"));
        form.appendChild(createInput("threeDSServerTransID", "${threeDSServerTransID}"));
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
      });
      function createInput(name, value) {
        var result = document.createElement("input");
        result.name = name;
        result.value = value;
        return result;
      }
    <\/script>`;

  const iframe = document.createElement("iframe");
  iframe.id = "3ds-fingerprint";
  iframe.style.display = "none";
  document.body.appendChild(iframe);
  const win = iframe.contentWindow;
  if (win) {
    const doc = win.document;
    win.name = "3DS Fingerprint";
    doc.open();
    doc.write(html);
    doc.close();
  }

  window.addEventListener("message", (m) => {
    if (m.data && m.data.type === "threeds-method-notification") {
      finish("complete");
    }
  });

  setTimeout(() => finish("timeout"), 10000);
}
