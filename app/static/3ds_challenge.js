function doChallenge(acsUrl, encodedCReq, state) {
  const html = `<script>
      document.addEventListener("DOMContentLoaded", function () {
        var form = document.createElement("form");
        form.method = "POST";
        form.action = "${acsUrl}";
        form.appendChild(createInput("creq", "${encodedCReq}"));
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

  const container = document.getElementById("challenge-container") || document.body;
  const iframe = document.createElement("iframe");
  iframe.id = "3ds-challenge";
  iframe.frameBorder = "0";
  iframe.style.display = "block";
  iframe.style.width = "100%";
  iframe.style.height = "100%";
  iframe.style.minHeight = "520px";
  iframe.style.background = "white";
  container.style.width = "100%";
  if (!container.style.height) {
    container.style.height = "70vh";
  }
  container.appendChild(iframe);

  const win = iframe.contentWindow;
  if (win) {
    const doc = win.document;
    win.name = "3DS Challenge";
    doc.open();
    doc.write(html);
    doc.close();
  }

  window.addEventListener("message", (m) => {
    if (m.data && m.data.type === "threeds-challenge-notification") {
      window.location = `/enroll/3ds/verify?state=${encodeURIComponent(state)}`;
    }
  });
}
