const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");


function fakeElement(value = "") {
    return {
        value,
        checked: false,
        textContent: "",
        placeholder: "",
        hidden: false,
        disabled: false,
        className: "",
        classList: {
            add() {},
            remove() {},
        },
        addEventListener() {},
    };
}


const notificationIds = [
    "notificationDiscordEnabled",
    "notificationDiscordWebhookUrl",
    "notificationDiscordWebhookUrlClear",
    "notificationPushoverEnabled",
    "notificationPushoverUserKey",
    "notificationPushoverUserKeyClear",
    "notificationPushoverApiToken",
    "notificationPushoverApiTokenClear",
    "notificationGotifyEnabled",
    "notificationGotifyServerUrl",
    "notificationGotifyToken",
    "notificationGotifyTokenClear",
    "notificationNtfyEnabled",
    "notificationNtfyServerUrl",
    "notificationNtfyTopic",
    "notificationNtfyToken",
    "notificationNtfyTokenClear",
    "notificationWebhookEnabled",
    "notificationWebhookUrl",
    "notificationWebhookUrlClear",
    "notificationEmailEnabled",
    "notificationEmailUsername",
    "notificationEmailAppPassword",
    "notificationEmailAppPasswordClear",
    "notificationEmailToAddress",
    "notificationSettingsStatus",
];

const elements = Object.fromEntries(
    notificationIds.map(
        (id) => [id, fakeElement()]
    )
);

const requests = [];

const context = {
    console,
    structuredClone,
    setInterval() {},
    localStorage: {
        getItem() {
            return null;
        },
        setItem() {},
    },
    document: {
        getElementById(id) {
            return elements[id] || null;
        },
        querySelectorAll() {
            return [];
        },
        createElement() {
            return fakeElement();
        },
    },
    async fetch(url, options) {
        const body = JSON.parse(options.body);
        requests.push({url, options, body});

        return {
            ok: true,
            async json() {
                return structuredClone(body);
            },
        };
    },
};

const publicConfig = {
    discord: {
        enabled: false,
        webhook_url: "",
        webhook_url_configured: false,
    },
    gotify: {
        enabled: false,
        server_url: "",
        token: "",
        token_configured: false,
    },
    pushover: {
        enabled: false,
        user_key: "",
        user_key_configured: false,
        api_token: "",
        api_token_configured: false,
    },
    ntfy: {
        enabled: false,
        server_url: "https://ntfy.sh",
        topic: "",
        token: "",
        token_configured: false,
    },
    webhook: {
        enabled: false,
        url: "",
        url_configured: false,
    },
    email: {
        enabled: true,
        username: "sender@workspace.example",
        app_password: "",
        app_password_configured: true,
        to_address: "recipient@example.net",
    },
};

const settingsTemplate = fs.readFileSync(
    path.join(
        __dirname,
        "../web_templates/alerts_settings_content.html"
    ),
    "utf8"
);

assert.match(
    settingsTemplate,
    /Email \(Gmail\)/
);
assert.match(
    settingsTemplate,
    /id="notificationEmailAppPassword"[\s\S]*type="password"[\s\S]*autocomplete="off"/
);
assert.match(
    settingsTemplate,
    /Google\s+App Password is required; do not enter your[\s\S]*normal Google account password/
);

vm.createContext(context);
vm.runInContext(
    fs.readFileSync(
        path.join(
            __dirname,
            "../static/alerts.js"
        ),
        "utf8"
    ),
    context
);


async function main() {
    context.renderNotificationConfig(publicConfig);

    assert.equal(
        elements.notificationEmailEnabled.checked,
        true
    );
    assert.equal(
        elements.notificationEmailUsername.value,
        "sender@workspace.example"
    );
    assert.equal(
        elements.notificationEmailAppPassword.value,
        ""
    );
    assert.equal(
        elements.notificationEmailAppPassword.placeholder,
        "Configured - leave blank to keep"
    );
    assert.equal(
        elements.notificationEmailAppPasswordClear.disabled,
        false
    );
    assert.equal(
        elements.notificationEmailToAddress.value,
        "recipient@example.net"
    );

    vm.runInContext(
        "currentNotificationConfig = " +
            JSON.stringify(publicConfig),
        context
    );

    await context.saveNotificationConfig();

    assert.equal(requests.length, 1);
    assert.equal(
        requests[0].url,
        "/api/notification-config"
    );
    assert.equal(
        requests[0].body.email.app_password,
        ""
    );
    assert.equal(
        requests[0].body.email.app_password_configured,
        true
    );

    elements.notificationEmailAppPasswordClear.checked = true;

    await context.saveNotificationConfig();

    assert.equal(requests.length, 2);
    assert.equal(
        requests[1].body.email.app_password,
        ""
    );
    assert.equal(
        requests[1].body.email.app_password_configured,
        false
    );

    console.log(
        "Gmail notification UI round-trip passed"
    );
}


main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
