/* script.js — jQuery + webflow.js + scripts de la page (ordre conservé,
   isolés par try/catch : un script en échec ne bloque pas les autres) */
/* chunk 0 */
try {
/* Ubepro — LP assurance consultants | formulaire, consentement, tracking, SMS et CRM */
(function () {
  'use strict';

  var DEFAULT_CONFIG = {
    leadApiUrl: 'https://mc.hellolead.pro/mon_compte/api/webflow/get_information.php',
    leadApiMode: 'nocors',
    leadApiCredentials: 'omit',
    googleScriptUrl: '',
    sheetTimeoutMs: 15000,
    formId: 'ADW_LP_ASSURANCE_CONSULTANT',
    source: 'LP CONSULTANTS',
    smsApiUrl: 'https://mc.hellolead.pro/mon_compte/api/smspartner/envoi_code_verification.php',
    smsCooldown: 120,
    debug: false
  };
  var CONFIG = Object.assign({}, DEFAULT_CONFIG, window.UBEPRO_CONFIG || {});
  var PREF_KEY = 'ubeproCookiePreferencesV1';
  var TRACKING_KEY = 'ubepro_tracking_v1';
  var PAGE_URL_KEY = 'ubepro_tracking_page_url_v1';
  var PARENT_URL_KEY = 'ubepro_public_landing_url_v1';
  var PARENT_BRIDGE_CHANNEL = 'ubepro-assurance-v1';
  var ALLOWED_PARENT_ORIGINS = ['https://www.comparateurpro.fr'];
  var parentBridgeNonce = '';
  var pendingSmsRequests = Object.create(null);
  function isAllowedParentOrigin(origin) {
    return ALLOWED_PARENT_ORIGINS.indexOf(origin) !== -1;
  }
  function resolveParentOrigin() {
    try {
      var origin = new URL(document.referrer).origin;
      if (isAllowedParentOrigin(origin)) return origin;
    } catch (error) {}
    return 'https://www.comparateurpro.fr';
  }
  var parentTargetOrigin = resolveParentOrigin();
  var VERSION = '2026-10-13-assurance.3';
  var entryUrl = typeof window.__UBEPRO_ENTRY_URL__ === 'string'
    ? window.__UBEPRO_ENTRY_URL__ : window.location.href;
  var parentLandingUrlReceived = window.parent === window;
  try {
    var initialEntry = new URL(entryUrl);
    if (isAllowedParentOrigin(initialEntry.origin) && initialEntry.pathname.replace(/\/+$/, '') === '/assurance-consultant-societe-conseil') {
      parentLandingUrlReceived = true;
    }
  } catch (error) {}

  var TRACKING_DEFS = [
    { key: 'source', aliases: ['ltm_source', 'utm_source', 'source'] },
    { key: 'categorie', aliases: ['categorie', 'utm_category', 'ltm_category', 'category'] },
    { key: 'user', aliases: ['user', 'utm_user', 'ltm_user'] },
    { key: 'utm_source', aliases: ['utm_source', 'ltm_source', 'source'] },
    { key: 'utm_medium', aliases: ['utm_medium', 'medium'] },
    { key: 'utm_campaign', aliases: ['utm_campaign', 'campaign'] },
    { key: 'utm_content', aliases: ['utm_content', 'content'] },
    { key: 'utm_term', aliases: ['utm_term', 'term'] },
    { key: 'utm_id', aliases: ['utm_id', 'campaign_id'] },
    { key: 'utm_category', aliases: ['utm_category', 'ltm_category', 'categorie', 'category'] },
    { key: 'utm_user', aliases: ['utm_user', 'ltm_user', 'user'] },
    { key: 'ltm_source', aliases: ['ltm_source', 'utm_source', 'source'] },
    { key: 'ltm_category', aliases: ['ltm_category', 'utm_category', 'categorie', 'category'] },
    { key: 'ltm_typ', aliases: ['ltm_typ', 'utm_typ', 'typ'] },
    { key: 'ltm_user', aliases: ['ltm_user', 'utm_user', 'user'] },
    { key: 'gclid', aliases: ['gclid'] },
    { key: 'msclkid', aliases: ['msclkid'] },
    { key: 'fbclid', aliases: ['fbclid'] }
  ];

  function clean(value, limit) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim().slice(0, limit || 500);
  }

  function cleanParam(value) {
    return clean(value, 500).replace(/[<>]/g, '');
  }

  function debugLog() {
    if (CONFIG.debug && window.console && console.log) {
      console.log.apply(console, ['[ubepro assurance]'].concat([].slice.call(arguments)));
    }
  }

  function readCookiePreferences() {
    var stored = null;
    try {
      stored = localStorage.getItem(PREF_KEY);
      if (stored) {
        var parsed = JSON.parse(stored);
        return {
          necessary: true,
          analytics: parsed.analytics === true,
          marketing: parsed.marketing === true,
          choiceMade: true
        };
      }
      var legacy = localStorage.getItem('cookiesChoice');
      if (legacy === 'accept') return { necessary: true, analytics: true, marketing: true, choiceMade: true };
      if (legacy === 'refuse') return { necessary: true, analytics: false, marketing: false, choiceMade: true };
    } catch (error) {}
    return { necessary: true, analytics: false, marketing: false, choiceMade: false };
  }

  var preferences = readCookiePreferences();
  window.__UBEPRO_COOKIE_PREFERENCES__ = preferences;

  function analyticsGranted() {
    return !!(window.__UBEPRO_COOKIE_PREFERENCES__ && window.__UBEPRO_COOKIE_PREFERENCES__.analytics === true);
  }

  function marketingGranted() {
    return !!(window.__UBEPRO_COOKIE_PREFERENCES__ && window.__UBEPRO_COOKIE_PREFERENCES__.marketing === true);
  }

  function trackingGranted() {
    return analyticsGranted() || marketingGranted();
  }

  function trackingKeyGranted(key) {
    if (key === 'gclid' || key === 'msclkid' || key === 'fbclid') return marketingGranted();
    return analyticsGranted();
  }

  function updateGoogleConsent(prefs) {
    if (typeof window.gtag !== 'function') return;
    window.gtag('consent', 'update', {
      analytics_storage: prefs.analytics ? 'granted' : 'denied',
      ad_storage: prefs.marketing ? 'granted' : 'denied',
      ad_user_data: prefs.marketing ? 'granted' : 'denied',
      ad_personalization: prefs.marketing ? 'granted' : 'denied'
    });
  }

  function parseUrlParams(rawUrl) {
    var params = Object.create(null);
    try {
      var url = new URL(rawUrl || window.location.href, window.location.href);
      function collect(search) {
        new URLSearchParams(search || '').forEach(function (value, key) {
          var normalizedKey = String(key).trim().toLowerCase();
          var normalizedValue = cleanParam(value);
          if (normalizedKey && normalizedValue) params[normalizedKey] = normalizedValue;
        });
      }
      collect(url.search);
      var hash = url.hash.slice(1);
      var hashQueryIndex = hash.indexOf('?');
      var hashQuery = hashQueryIndex >= 0
        ? hash.slice(hashQueryIndex + 1)
        : (hash.indexOf('=') >= 0 && hash.charAt(0) !== '/' ? hash : '');
      collect(hashQuery);
    } catch (error) {}
    return params;
  }

  function readStoredTracking() {
    if (!trackingGranted()) return {};
    try {
      var saved = JSON.parse(sessionStorage.getItem(TRACKING_KEY) || '{}');
      if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {};
      var result = {};
      TRACKING_DEFS.forEach(function (def) {
        if (trackingKeyGranted(def.key) && typeof saved[def.key] === 'string') {
          var value = cleanParam(saved[def.key]);
          if (value) result[def.key] = value;
        }
      });
      return result;
    } catch (error) {
      return {};
    }
  }

  var trackingValues = parentLandingUrlReceived ? readStoredTracking() : {};
  var trackedPageUrl = '';
  if (analyticsGranted() && parentLandingUrlReceived) {
    trackedPageUrl = clean(entryUrl, 1000);
    try {
      var savedPageUrl = sessionStorage.getItem(PAGE_URL_KEY);
      if (savedPageUrl && Object.keys(trackingValues).length) trackedPageUrl = clean(savedPageUrl, 1000);
    } catch (error) {}
  }

  function purgeUnconsentedTracking() {
    var retained = {};
    TRACKING_DEFS.forEach(function (def) {
      if (trackingKeyGranted(def.key) && trackingValues[def.key]) retained[def.key] = trackingValues[def.key];
    });
    trackingValues = retained;
    if (parentLandingUrlReceived && trackingGranted()) {
      var filteredEntry = filterUrlByConsent(entryUrl);
      if (filteredEntry) entryUrl = filteredEntry;
    } else if (parentLandingUrlReceived && window.parent !== window) {
      try {
        var entryBase = new URL(entryUrl);
        entryBase.search = '';
        entryBase.hash = '';
        entryUrl = entryBase.href;
      } catch (error) {}
    }
    window.__UBEPRO_ENTRY_URL__ = entryUrl;
    try {
      if (Object.keys(retained).length) sessionStorage.setItem(TRACKING_KEY, JSON.stringify(retained));
      else sessionStorage.removeItem(TRACKING_KEY);
      if (parentLandingUrlReceived && trackingGranted()) sessionStorage.setItem(PARENT_URL_KEY, entryUrl);
      else sessionStorage.removeItem(PARENT_URL_KEY);
      if (analyticsGranted() && parentLandingUrlReceived) {
        trackedPageUrl = clean(filterUrlByConsent(entryUrl), 1000);
        if (trackedPageUrl) sessionStorage.setItem(PAGE_URL_KEY, trackedPageUrl);
      } else {
        trackedPageUrl = '';
        sessionStorage.removeItem(PAGE_URL_KEY);
      }
    } catch (error) {}
  }

  purgeUnconsentedTracking();

  function captureTracking(rawUrl) {
    if (!trackingGranted()) return Object.assign({}, trackingValues);
    var params = parseUrlParams(rawUrl || window.location.href);
    var found = {};
    TRACKING_DEFS.forEach(function (def) {
      if (!trackingKeyGranted(def.key)) return;
      var alias = def.aliases.find(function (candidate) {
        return params[candidate] !== undefined && params[candidate] !== '';
      });
      if (alias) found[def.key] = params[alias];
    });
    if (Object.keys(found).length) {
      trackingValues = Object.assign({}, trackingValues, found);
      try { sessionStorage.setItem(TRACKING_KEY, JSON.stringify(trackingValues)); } catch (error) {}
      if (analyticsGranted()) {
        trackedPageUrl = clean(filterUrlByConsent(rawUrl || window.location.href), 1000);
        try { sessionStorage.setItem(PAGE_URL_KEY, trackedPageUrl); } catch (error) {}
      }
    }
    return Object.assign({}, trackingValues);
  }

  function getCurrentUrlCategory() {
    var current = parseUrlParams(window.location.href);
    var entry = parseUrlParams(entryUrl);
    return current.categorie || current.utm_category || current.ltm_category || current.category ||
      entry.categorie || entry.utm_category || entry.ltm_category || entry.category || '';
  }

  function getTrackingPayload() {
    if (trackingGranted()) {
      captureTracking(entryUrl);
      captureTracking(window.location.href);
    }
    var result = {};
    TRACKING_DEFS.forEach(function (def) {
      result[def.key] = trackingKeyGranted(def.key) ? cleanParam(trackingValues[def.key] || '') : '';
    });
    return result;
  }

  function isAnalyticsUrlParam(key) {
    var normalized = String(key || '').toLowerCase();
    return /^(utm_|ltm_)/.test(normalized) ||
      ['source', 'categorie', 'category', 'medium', 'campaign', 'content', 'term', 'user', 'campaign_id'].indexOf(normalized) !== -1;
  }

  function filterUrlByConsent(rawUrl) {
    if (!trackingGranted()) return '';
    try {
      var url = new URL(String(rawUrl || ''));
      var keys = [];
      url.searchParams.forEach(function (value, key) { keys.push(key); });
      keys.forEach(function (key) {
        var normalized = key.toLowerCase();
        if (!analyticsGranted() && isAnalyticsUrlParam(normalized)) url.searchParams.delete(key);
        if (!marketingGranted() && ['gclid', 'msclkid', 'fbclid'].indexOf(normalized) !== -1) url.searchParams.delete(key);
      });
      return url.href.slice(0, 2000);
    } catch (error) {
      return '';
    }
  }

  function sanitizePublicLandingUrl(rawUrl) {
    if (!trackingGranted()) return '';
    try {
      var url = new URL(String(rawUrl || ''));
      if (!isAllowedParentOrigin(url.origin)) return '';
      if (url.pathname.replace(/\/+$/, '') !== '/assurance-consultant-societe-conseil') return '';
      return filterUrlByConsent(url.href);
    } catch (error) {
      return '';
    }
  }

  function safeReferrer() {
    try {
      var referrer = new URL(document.referrer);
      return clean(referrer.origin + referrer.pathname, 1000);
    } catch (error) {
      return '';
    }
  }

  function parentBridgePost(message) {
    if (window.parent === window) return false;
    var payload = Object.assign({ channel: PARENT_BRIDGE_CHANNEL }, message || {});
    if (parentBridgeNonce && payload.type !== 'bridge-ready') payload.nonce = parentBridgeNonce;
    try {
      window.parent.postMessage(payload, parentTargetOrigin);
      return true;
    } catch (error) {
      return false;
    }
  }

  function sendConsentStateToParent() {
    if (!parentBridgeNonce) return;
    parentBridgePost({
      type: 'consent-state',
      choiceMade: !!preferences.choiceMade,
      analytics: analyticsGranted(),
      marketing: marketingGranted()
    });
  }

  function applyPublicLandingUrl(rawUrl) {
    var publicUrl = sanitizePublicLandingUrl(rawUrl);
    if (!publicUrl) return;
    var priorUrl = '';
    try { priorUrl = sessionStorage.getItem(PARENT_URL_KEY) || ''; } catch (error) {}
    if (priorUrl !== publicUrl) {
      trackingValues = {};
      trackedPageUrl = '';
      try {
        sessionStorage.removeItem(TRACKING_KEY);
        sessionStorage.removeItem(PAGE_URL_KEY);
      } catch (error) {}
    }
    entryUrl = publicUrl;
    parentLandingUrlReceived = true;
    window.__UBEPRO_ENTRY_URL__ = entryUrl;
    captureTracking(entryUrl);
    if (analyticsGranted()) {
      trackedPageUrl = clean(entryUrl, 1000);
      try { sessionStorage.setItem(PAGE_URL_KEY, trackedPageUrl); } catch (error) {}
    } else {
      trackedPageUrl = '';
      try { sessionStorage.removeItem(PAGE_URL_KEY); } catch (error) {}
    }
    try { sessionStorage.setItem(PARENT_URL_KEY, entryUrl); } catch (error) {}
    if (categoryField) {
      var category = getCurrentUrlCategory();
      if (category) categoryField.value = category;
    }
  }

  window.addEventListener('message', function (event) {
    if (event.source !== window.parent || !isAllowedParentOrigin(event.origin)) return;
    var message = event.data;
    if (!message || message.channel !== PARENT_BRIDGE_CHANNEL) return;
    if (message.type === 'bridge-init' && typeof message.nonce === 'string' && message.nonce.length >= 16) {
      parentBridgeNonce = message.nonce;
      sendConsentStateToParent();
      return;
    }
    if (!parentBridgeNonce || message.nonce !== parentBridgeNonce) return;
    if (message.type === 'landing-url') {
      applyPublicLandingUrl(message.url);
    } else if (message.type === 'sms-response') {
      var pending = pendingSmsRequests[message.requestId];
      if (!pending) return;
      window.clearTimeout(pending.timer);
      delete pendingSmsRequests[message.requestId];
      pending.resolve({
        status: Number(message.status) || 0,
        ok: message.ok === true,
        data: message.data && typeof message.data === 'object' ? message.data : {}
      });
    }
  });

  window.__UBEPRO_ENTRY_URL__ = entryUrl;
  captureTracking(entryUrl);
  captureTracking(window.location.href);
  window.ubeproTracking = Object.freeze({
    version: VERSION,
    inspect: function () {
      return {
        version: VERSION,
        current_url: clean(entryUrl || window.location.href, 1000),
        page_url: analyticsGranted() ? clean(trackedPageUrl, 1000) : '',
        values: getTrackingPayload()
      };
    }
  });
  if (window.parent !== window) parentBridgePost({ type: 'bridge-ready' });

  /* ---------- Préférences cookies ---------- */
  var cookieBanner = document.getElementById('cookies');
  var manageCookies = document.getElementById('manageCookies');
  var cookiePreferencesPanel = document.getElementById('cookiePreferences');
  var analyticsCheckbox = document.getElementById('analyticsCookies');
  var marketingCheckbox = document.getElementById('marketingCookies');

  function setPreferences(nextPreferences) {
    preferences = {
      necessary: true,
      analytics: nextPreferences.analytics === true,
      marketing: nextPreferences.marketing === true,
      choiceMade: true
    };
    window.__UBEPRO_COOKIE_PREFERENCES__ = preferences;
    try { localStorage.setItem(PREF_KEY, JSON.stringify(preferences)); } catch (error) {}
    updateGoogleConsent(preferences);
    purgeUnconsentedTracking();
    captureTracking(entryUrl);
    captureTracking(window.location.href);
    sendConsentStateToParent();
    if (cookieBanner) cookieBanner.hidden = true;
    if (cookiePreferencesPanel) cookiePreferencesPanel.hidden = true;
  }

  if (cookieBanner) {
    cookieBanner.hidden = preferences.choiceMade;
    if (analyticsCheckbox) analyticsCheckbox.checked = preferences.analytics;
    if (marketingCheckbox) marketingCheckbox.checked = preferences.marketing;

    cookieBanner.querySelectorAll('[data-cookie]').forEach(function (button) {
      button.addEventListener('click', function () {
        var action = button.getAttribute('data-cookie');
        if (action === 'accept') {
          setPreferences({ analytics: true, marketing: true });
        } else if (action === 'refuse') {
          setPreferences({ analytics: false, marketing: false });
        } else if (action === 'prefs') {
          if (cookiePreferencesPanel) cookiePreferencesPanel.hidden = false;
          if (analyticsCheckbox) analyticsCheckbox.checked = preferences.analytics;
          if (marketingCheckbox) marketingCheckbox.checked = preferences.marketing;
        }
      });
    });

    var saveCookiePreferences = cookieBanner.querySelector('[data-cookie-save]');
    if (saveCookiePreferences) {
      saveCookiePreferences.addEventListener('click', function () {
        setPreferences({
          analytics: !!(analyticsCheckbox && analyticsCheckbox.checked),
          marketing: !!(marketingCheckbox && marketingCheckbox.checked)
        });
      });
    }
  }

  if (manageCookies && cookieBanner) {
    manageCookies.addEventListener('click', function (event) {
      event.preventDefault();
      cookieBanner.hidden = false;
      if (cookiePreferencesPanel) cookiePreferencesPanel.hidden = false;
      if (analyticsCheckbox) analyticsCheckbox.checked = preferences.analytics;
      if (marketingCheckbox) marketingCheckbox.checked = preferences.marketing;
    });
  }

  /* ---------- Formulaire multi-étapes ---------- */
  var form = document.getElementById('leadForm');
  if (!form) return;

  var formConfig = Object.assign({}, CONFIG, {
    leadApiUrl: form.getAttribute('data-api-endpoint') || CONFIG.leadApiUrl,
    leadApiMode: form.getAttribute('data-api-mode') || CONFIG.leadApiMode,
    formId: form.getAttribute('data-form-id') || CONFIG.formId,
    smsApiUrl: form.getAttribute('data-sms-endpoint') || CONFIG.smsApiUrl,
    googleScriptUrl: form.getAttribute('data-google-script-url') || CONFIG.googleScriptUrl,
    source: form.getAttribute('data-source') || CONFIG.source
  });

  var steps = Array.prototype.slice.call(form.querySelectorAll('.step[data-step]'))
    .filter(function (step) { return step.getAttribute('data-step') !== 'done'; });
  var done = form.querySelector('.step-done');
  var doneTitle = document.getElementById('doneTitle');
  var doneMessage = document.getElementById('doneMessage');
  var prev = document.getElementById('prev');
  var next = document.getElementById('next');
  var bar = document.getElementById('bar');
  var count = document.getElementById('stepCount');
  var nav = document.getElementById('nav');
  var formError = document.getElementById('formError');
  var current = 0;
  var sending = false;
  var originalRequired = new WeakMap();
  var smsVerified = false;
  var verifiedPhone = '';
  var requestedPhone = '';
  var smsCountdown = null;
  var submissionId = makeId();
  var categoryField = form.querySelector('[name="categorie"]');
  if (categoryField && getCurrentUrlCategory()) categoryField.value = getCurrentUrlCategory();

  form.querySelectorAll('input, select, textarea').forEach(function (field) {
    originalRequired.set(field, field.required);
  });

  function makeId() {
    try {
      if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    } catch (error) {}
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (char) {
      var random = Math.random() * 16 | 0;
      var value = char === 'x' ? random : (random & 3 | 8);
      return value.toString(16);
    });
  }


  function checked(selector) {
    return !!form.querySelector(selector + ':checked');
  }

  function toggleGroup(groupName, visible) {
    var group = form.querySelector('[data-condition-group="' + groupName + '"]');
    if (!group) return;
    group.hidden = !visible;
    group.setAttribute('aria-hidden', visible ? 'false' : 'true');
    group.querySelectorAll('input, select, textarea').forEach(function (field) {
      if (visible) {
        field.disabled = false;
        field.required = originalRequired.get(field) === true;
      } else {
        if (field.type === 'checkbox' || field.type === 'radio') field.checked = false;
        else if (field.type !== 'hidden') field.value = '';
        field.required = false;
        field.disabled = true;
      }
    });
  }

  function syncConditions() {
    var multirisque = checked('input[data-assurance="multirisque"]');
    var solo = checked('input[data-effectif="0-1"]');
    var tns = checked('input[data-statut-dirigeant="tns"]');
    var autre = checked('input[data-autre-mrp]');
    toggleGroup('mrp', multirisque);
    toggleGroup('mrp-autre', multirisque && autre);
    toggleGroup('psi', checked('input[data-assurance="sociale-individuelle"]'));
    toggleGroup('psc', checked('input[data-assurance="sociale-collective"]'));
    toggleGroup('statut-dirigeant', solo);
    toggleGroup('auto-entrepreneur', solo && tns);
  }

  function scrollToForm() {
    var offset = parseInt(form.getAttribute('data-scroll-top-offset') || '90', 10);
    if (!isFinite(offset)) offset = 90;
    var top = form.getBoundingClientRect().top + window.pageYOffset - offset;
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
  }

  function currentPhone() {
    return normalizePhone(textValue('telephone'));
  }

  function consentOk() {
    return radioValue('consentement') === 'oui';
  }

  function updateNextButton() {
    if (!next) return;
    next.disabled = sending || (current === steps.length - 1 && !smsVerified);
    if (sending) next.textContent = 'Envoi…';
    else next.textContent = current === steps.length - 1 ? 'Envoyer ma demande' : 'Suivant';
  }

  function render(shouldScroll) {
    steps.forEach(function (step, index) {
      step.classList.toggle('is-active', index === current);
    });
    if (bar) bar.style.width = (((current + 1) / steps.length) * 100) + '%';
    if (count) count.textContent = 'Étape ' + (current + 1) + ' sur ' + steps.length;
    if (prev) prev.disabled = current === 0;
    if (formError) formError.textContent = '';
    updateNextButton();
    if (shouldScroll && form.getAttribute('data-scroll-top') === 'true') {
      window.requestAnimationFrame(scrollToForm);
    }
  }

  function setStepError(message) {
    var error = steps[current].querySelector('[data-err]');
    if (error) error.textContent = message;
    return false;
  }

  function validateStep() {
    var step = steps[current];
    var key = step.getAttribute('data-step');
    var error = step.querySelector('[data-err]');
    if (error) error.textContent = '';

    if (key === '1') {
      if (!step.querySelector('input[data-assurance]:checked')) {
        return setStepError('Sélectionnez au moins un type d’assurance.');
      }
      return true;
    }
    if (key === '2') {
      if (!step.querySelector('input[name="reponse_4"]:checked')) {
        return setStepError('Indiquez l’effectif de votre structure.');
      }
      if (checked('input[data-effectif="0-1"]') && !step.querySelector('input[name="reponse_7"]:checked')) {
        return setStepError('Précisez le statut du dirigeant.');
      }
      if (checked('input[data-effectif="0-1"]') && checked('input[data-statut-dirigeant="tns"]') &&
          !step.querySelector('input[name="reponse_3"]:checked')) {
        return setStepError('Indiquez si vous êtes auto-entrepreneur.');
      }
      return true;
    }
    if (key === '3' && !step.querySelector('input[name="reponse_8"]:checked')) {
      return setStepError('Indiquez si la société existe ou est en cours de création.');
    }
    if (key === '4') {
      if (!textValue('prenom') || !textValue('nom')) return setStepError('Renseignez votre prénom et votre nom.');
    }
    if (key === '5') {
      var emailField = form.querySelector('[name="mail"]');
      var emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
      if (!emailField || !emailPattern.test(textValue('mail'))) return setStepError('Indiquez une adresse e-mail valide.');
    }
    if (key === '6') {
      var postal = textValue('code_postal').replace(/\s+/g, '');
      if (!textValue('societe')) return setStepError('Indiquez le nom de la société.');
      if (!/^\d{5}$/.test(postal)) return setStepError('Indiquez un code postal à cinq chiffres.');
    }
    if (key === '7') {
      if (!/^0[67]\d{8}$/.test(currentPhone())) return setStepError('Saisissez un mobile français valide (10 chiffres, 06 ou 07).');
      if (!smsVerified || verifiedPhone !== currentPhone()) return setStepError('Vérifiez votre numéro par SMS avant de continuer.');
      if (!consentOk()) return setStepError('Veuillez accepter l’utilisation de vos informations avant de valider.');
    }
    return true;
  }

  function textValue(name) {
    var field = form.querySelector('[name="' + name + '"]');
    return field ? String(field.value || '').trim() : '';
  }

  function radioValue(name) {
    var field = form.querySelector('input[name="' + name + '"]:checked');
    return field ? String(field.value || '').trim() : '';
  }

  function normalizePhone(value) {
    var phone = String(value || '').trim().replace(/[\s().-]/g, '');
    if (/^\+?0033/.test(phone)) return '0' + phone.replace(/^\+?0033/, '').replace(/\D/g, '');
    if (/^\+33/.test(phone)) return '0' + phone.slice(3).replace(/\D/g, '');
    if (/^33\d{9}$/.test(phone)) return '0' + phone.slice(2);
    return phone.replace(/\D/g, '');
  }

  function formatPhone(value) {
    var digits = normalizePhone(value);
    if (/^0\d{1,9}$/.test(digits)) return digits.replace(/(\d{2})(?=\d)/g, '$1 ').trim();
    return value;
  }

  function labelFor(input) {
    var label = input.closest ? input.closest('label') : null;
    var strong = label && label.querySelector('.opt-body strong');
    var span = label && label.querySelector('span');
    return clean(strong ? strong.textContent : (span ? span.textContent : input.value), 200);
  }

  function checkedLabels(selector) {
    return Array.prototype.slice.call(form.querySelectorAll(selector + ':checked'))
      .map(labelFor).filter(Boolean);
  }

  function summaryAndAnswers() {
    var insurance = checkedLabels('input[data-assurance]');
    var mrp = checkedLabels('input[name^="reponse_2_"]');
    var psi = checkedLabels('input[name^="reponse_5_"]');
    var psc = checkedLabels('input[name^="reponse_6_"]');
    var otherMrp = textValue('reponse_champ_2_8');
    if (otherMrp) mrp = mrp.filter(function (label) { return label !== 'Autre'; });
    var mrpAnswer = mrp.join(', ');
    if (otherMrp) mrpAnswer += (mrpAnswer ? ', ' : '') + 'Autre : ' + otherMrp;
    var effectif = radioValue('reponse_4');
    var statut = radioValue('reponse_7');
    var auto = radioValue('reponse_3');
    var companyState = radioValue('reponse_8');
    var summary = [];
    if (insurance.length) summary.push('Assurances recherchées : ' + insurance.join(', '));
    if (mrpAnswer) summary.push('Garanties multirisque : ' + mrpAnswer);
    if (psi.length) summary.push('Protection sociale individuelle : ' + psi.join(', '));
    if (psc.length) summary.push('Protection sociale collective : ' + psc.join(', '));
    if (effectif) summary.push('Effectif : ' + effectif);
    if (statut) summary.push('Statut du dirigeant : ' + statut);
    if (auto) summary.push('Auto-entrepreneur : ' + auto);
    if (companyState) summary.push('État de la société : ' + companyState);
    return {
      insurance: insurance,
      mrp: mrpAnswer,
      psi: psi.join(', '),
      psc: psc.join(', '),
      effectif: effectif,
      statut: statut,
      auto: auto,
      companyState: companyState,
      autreInfo: summary.join('\n')
    };
  }

  function makeCrmEnvelope(data) {
    return {
      payload: {
        formId: formConfig.formId,
        id: submissionId,
        data: data
      }
    };
  }

  function sendCrm(data) {
    if (!formConfig.leadApiUrl || formConfig.leadApiMode === 'off') {
      return Promise.reject(new Error('API CRM désactivée ou URL absente.'));
    }
    var body = JSON.stringify(makeCrmEnvelope(data));
    if (formConfig.leadApiMode === 'cors') {
      var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var timer = controller ? window.setTimeout(function () { controller.abort(); }, 6000) : null;
      return fetch(formConfig.leadApiUrl, {
        method: 'POST',
        mode: 'cors',
        credentials: formConfig.leadApiCredentials === 'include' ? 'include' : 'omit',
        headers: { 'Content-Type': 'application/json; charset=UTF-8' },
        body: body,
        signal: controller ? controller.signal : undefined
      }).then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.json().catch(function () { return null; }).then(function (json) {
          if (!json || json.status !== 'ok') throw new Error((json && json.message) || 'Réponse CRM inattendue.');
          return { state: 'ok', confirmed: true, via: 'cors', response: json };
        });
      }).finally(function () { if (timer) window.clearTimeout(timer); });
    }

    try {
      if (navigator.sendBeacon) {
        var blob = new Blob([body], { type: 'text/plain;charset=UTF-8' });
        if (navigator.sendBeacon(formConfig.leadApiUrl, blob)) {
          return Promise.resolve({ state: 'unverified', confirmed: false, via: 'beacon' });
        }
      }
    } catch (error) {
      debugLog('sendBeacon CRM échoué; repli fetch.', error);
    }

    var controllerNoCors = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timerNoCors = controllerNoCors ? window.setTimeout(function () { controllerNoCors.abort(); }, 6000) : null;
    return fetch(formConfig.leadApiUrl, {
      method: 'POST',
      mode: 'no-cors',
      credentials: formConfig.leadApiCredentials === 'include' ? 'include' : 'omit',
      headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
      body: body,
      keepalive: true,
      signal: controllerNoCors ? controllerNoCors.signal : undefined
    }).then(function () {
      return { state: 'unverified', confirmed: false, via: 'fetch-no-cors' };
    }).finally(function () { if (timerNoCors) window.clearTimeout(timerNoCors); });
  }

  function buildSheetData(data) {
    // Le Apps Script partagé attend des champs plats (e.parameter), avec q1..q3.
    // Les réponses consultants supplémentaires sont conservées dans la colonne « enjeu ».
    var sheetData = {
      form_id: formConfig.formId,
      id_lead: submissionId,
      civilite: '',
      nom: data.nom || '',
      prenom: data.prenom || '',
      mail: data.mail || '',
      telephone: data.telephone || '',
      societe: data.societe || '',
      code_postal: data.code_postal || '',
      ville: '',
      site: '',
      solution: clean(data.reponse_1 || '', 500),
      enjeu: clean(data.autre_info_fj || '', 500),
      question_1: data.question_1 || '',
      reponse_1: data.reponse_1 || '',
      question_2: data.question_2 || '',
      reponse_2: data.reponse_2 || '',
      question_3: data.question_3 || '',
      reponse_3: data.reponse_3 || '',
      source: data.source || formConfig.source,
      categorie: data.categorie || '',
      website: ''
    };
    [
      'user', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term',
      'utm_id', 'utm_category', 'utm_user', 'ltm_source', 'ltm_category', 'ltm_typ',
      'ltm_user', 'gclid', 'msclkid', 'fbclid', 'page_url', 'page_referrer',
      'user_agent', 'langue'
    ].forEach(function (key) {
      if (data[key]) sheetData[key] = data[key];
    });
    return sheetData;
  }

  function sendToGoogleSheets(data) {
    if (!formConfig.googleScriptUrl) {
      return Promise.reject(new Error('URL Google Apps Script manquante.'));
    }
    var body = new URLSearchParams();
    var sheetData = buildSheetData(data);
    Object.keys(sheetData).forEach(function (key) {
      body.append(key, String(sheetData[key] == null ? '' : sheetData[key]));
    });

    var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = controller ? window.setTimeout(function () {
      controller.abort();
    }, formConfig.sheetTimeoutMs || 15000) : null;

    return fetch(formConfig.googleScriptUrl, {
      method: 'POST',
      mode: 'cors',
      credentials: 'omit',
      body: body,
      signal: controller ? controller.signal : undefined
    }).then(function (response) {
      // Apps Script peut répondre HTTP 200 avec status:error : valider le JSON, pas seulement response.ok.
      return response.json().catch(function () { return null; }).then(function (json) {
        if (!response.ok) throw new Error('HTTP ' + response.status + (json && json.message ? ': ' + json.message : ''));
        if (!json || json.status !== 'ok') {
          throw new Error((json && json.message) || 'Réponse Google Sheets inattendue.');
        }
        return { state: 'ok', confirmed: true, response: json };
      });
    }).finally(function () {
      if (timer) window.clearTimeout(timer);
    });
  }

  function normalizeSmsResult(response) {
    // Lire le JSON même pour les réponses HTTP 4xx/5xx : il peut contenir le message utile.
    return response.json().catch(function () { return {}; }).then(function (data) {
      return { status: response.status, ok: response.ok, data: data };
    });
  }

  function smsStatusCode(result) {
    if (result.status >= 400) return result.status;
    var data = result.data || {};
    var code = parseInt(data.http_status || data.status_code || data.error_code, 10);
    return code >= 400 && code <= 599 ? code : result.status;
  }

  function smsSucceeded(result) {
    if (!result.ok || smsStatusCode(result) >= 400) return false;
    var data = result.data || {};
    if (data.ok === false || data.success === false) return false;
    var state = String(data.status || data.statut || '').toLowerCase();
    return !/^(error|erreur|ko|failed|fail)$/.test(state);
  }

  function smsRequest(params) {
    if (window.parent === window) {
      return fetch(formConfig.smsApiUrl, {
        method: 'POST',
        mode: 'cors',
        credentials: 'omit',
        body: new URLSearchParams(params)
      }).then(normalizeSmsResult);
    }
    if (!parentBridgeNonce) return Promise.reject(new Error('Pont SMS de la page publique indisponible.'));
    return new Promise(function (resolve, reject) {
      var requestId = makeId();
      var payload = {
        action: String(params.action || ''),
        telephone: String(params.telephone || '')
      };
      if (params.code != null) payload.code = String(params.code);
      var timer = window.setTimeout(function () {
        delete pendingSmsRequests[requestId];
        reject(new Error('Délai dépassé pour la requête SMS.'));
      }, 15000);
      pendingSmsRequests[requestId] = { resolve: resolve, reject: reject, timer: timer };
      if (!parentBridgePost({ type: 'sms-request', requestId: requestId, params: payload })) {
        window.clearTimeout(timer);
        delete pendingSmsRequests[requestId];
        reject(new Error('Impossible de joindre la page publique pour le SMS.'));
      }
    });
  }

  function smsErrorText(result) {
    var fallback = {
      422: 'Numéro ou code invalide.',
      404: 'Aucun code envoyé pour ce numéro. Cliquez sur « Recevoir le code ».',
      410: 'Le code a expiré. Demandez-en un nouveau.',
      409: 'Ce code a déjà été utilisé. Demandez-en un nouveau.',
      429: 'Veuillez patienter avant de redemander un code.',
      502: 'L’envoi du SMS a échoué. Réessayez dans un instant.'
    };
    var status = smsStatusCode(result);
    return (result.data && (result.data.message || result.data.error)) || fallback[status] || 'Une erreur est survenue.';
  }

  function initSmsVerification() {
    var phone = form.querySelector('input[name="telephone"]');
    if (!phone) return;
    var existing = form.querySelector('.sms-verification');
    if (existing) return;

    var box = document.createElement('div');
    box.className = 'sms-verification';
    box.innerHTML =
      '<button type="button" class="btn btn-primary btn-small sms-send">Recevoir le code</button>' +
      '<p class="sms-help">Code à 6 chiffres, valable 10 minutes et à usage unique. Un nouveau code remplace le précédent.</p>' +
      '<div class="sms-code-wrap" hidden>' +
        '<input type="text" class="sms-code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code" placeholder="Code à 6 chiffres" aria-label="Code de vérification SMS"> ' +
        '<button type="button" class="btn btn-ghost btn-small sms-check">Vérifier</button>' +
      '</div>' +
      '<p class="sms-message" role="status" aria-live="polite"></p>';
    var phoneLabel = phone.closest ? phone.closest('label') : null;
    (phoneLabel || phone).insertAdjacentElement('afterend', box);

    var sendButton = box.querySelector('.sms-send');
    var checkButton = box.querySelector('.sms-check');
    var codeWrap = box.querySelector('.sms-code-wrap');
    var codeInput = box.querySelector('.sms-code');
    var message = box.querySelector('.sms-message');
    var flag = form.querySelector('input[name="telephone_verifie"]');
    if (!flag) {
      flag = document.createElement('input');
      flag.type = 'hidden';
      flag.name = 'telephone_verifie';
      form.appendChild(flag);
    }
    flag.value = 'non';

    function say(text, success) {
      message.textContent = text || '';
      message.classList.toggle('is-success', !!success);
      message.classList.toggle('is-error', !!text && !success);
    }

    function countdown(seconds) {
      if (smsCountdown) window.clearInterval(smsCountdown);
      sendButton.disabled = true;
      function tick() {
        if (seconds <= 0) {
          window.clearInterval(smsCountdown);
          smsCountdown = null;
          sendButton.disabled = false;
          sendButton.textContent = 'Renvoyer le code';
          return;
        }
        sendButton.textContent = 'Renvoyer le code (' + seconds + ' s)';
        seconds -= 1;
      }
      tick();
      smsCountdown = window.setInterval(tick, 1000);
    }

    sendButton.addEventListener('click', function () {
      var number = currentPhone();
      if (!/^0[67]\d{8}$/.test(number)) {
        say('Saisissez un mobile français valide (10 chiffres, 06 ou 07).');
        return;
      }
      requestedPhone = number;
      sendButton.disabled = true;
      say('Envoi en cours…', true);
      smsRequest({ action: 'envoyer_code', telephone: number }).then(function (result) {
        if (smsSucceeded(result)) {
          codeWrap.hidden = false;
          codeInput.value = '';
          codeInput.focus();
          say('Code envoyé par SMS.', true);
          countdown(formConfig.smsCooldown || 120);
        } else if (smsStatusCode(result) === 429) {
          var data = result.data || {};
          var wait = parseInt(data.retry_after || data.retryAfter || data.delai || data.delai_restant ||
            data.restant || data.remaining || data.seconds_remaining, 10);
          if (!wait) {
            var match = smsErrorText(result).match(/\d+/);
            wait = match ? parseInt(match[0], 10) : (formConfig.smsCooldown || 120);
          }
          say(smsErrorText(result) + ' Délai restant : ' + wait + ' s.');
          countdown(wait);
        } else {
          say(smsErrorText(result));
          sendButton.disabled = false;
          sendButton.textContent = 'Recevoir le code';
        }
      }).catch(function () {
        say('Connexion impossible au service SMS. Vérifiez l’origine autorisée puis réessayez.');
        sendButton.disabled = false;
      });
    });

    function verifyCode() {
      var number = currentPhone();
      var code = String(codeInput.value || '').replace(/\D/g, '');
      if (!/^0[67]\d{8}$/.test(number)) return say('Vérifiez le numéro de téléphone saisi.');
      if (number !== requestedPhone) return say('Le numéro a changé. Demandez un nouveau code.');
      if (code.length !== 6) return say('Le code comporte 6 chiffres.');
      checkButton.disabled = true;
      smsRequest({ action: 'verifier_code', telephone: number, code: code }).then(function (result) {
        checkButton.disabled = false;
        if (smsSucceeded(result)) {
          smsVerified = true;
          verifiedPhone = number;
          flag.value = 'oui';
          if (smsCountdown) window.clearInterval(smsCountdown);
          smsCountdown = null;
          codeWrap.hidden = true;
          sendButton.hidden = true;
          say('✓ Numéro vérifié.', true);
          updateNextButton();
        } else {
          say(smsErrorText(result));
        }
      }).catch(function () {
        checkButton.disabled = false;
        say('Connexion impossible au service de vérification. Réessayez.');
      });
    }

    checkButton.addEventListener('click', verifyCode);
    codeInput.addEventListener('input', function () {
      codeInput.value = String(codeInput.value || '').replace(/\D/g, '').slice(0, 6);
    });
    codeInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        verifyCode();
      }
    });

    phone.addEventListener('input', function () {
      var formatted = formatPhone(phone.value);
      if (phone.value !== formatted) phone.value = formatted;
      var number = currentPhone();
      if ((smsVerified && number !== verifiedPhone) || (requestedPhone && number !== requestedPhone)) {
        smsVerified = false;
        verifiedPhone = '';
        requestedPhone = '';
        flag.value = 'non';
        codeWrap.hidden = true;
        codeInput.value = '';
        sendButton.hidden = false;
        sendButton.disabled = false;
        sendButton.textContent = 'Recevoir le code';
        if (smsCountdown) window.clearInterval(smsCountdown);
        smsCountdown = null;
        say('Le numéro a changé. Demandez un nouveau code.');
      }
      updateNextButton();
    });
  }

  function showDone(delivery) {
    steps.forEach(function (step) { step.classList.remove('is-active'); });
    if (done) done.classList.add('is-active');
    if (nav) nav.style.display = 'none';
    if (bar) bar.style.width = '100%';
    if (count) count.textContent = 'Demande envoyée';
    if (doneTitle) doneTitle.textContent = 'Merci, votre demande a bien été reçue !';
    if (doneMessage) {
      if (delivery && (delivery.sheetStatus === 'ok' || delivery.crmStatus !== 'error')) {
        doneMessage.textContent = 'Vous recevrez prochainement un SMS vous précisant quelle(s) compagnie(s) d’assurances prendront contact avec vous.';
      } else {
        doneMessage.textContent = 'Votre demande a été transmise, mais sa confirmation est en cours de vérification.';
      }
    }
    window.requestAnimationFrame(scrollToForm);
    if (delivery && delivery.crmStatus === 'unverified') {
      debugLog('CRM transporté en no-cors; insertion finale non vérifiable côté navigateur.');
    }
    if (delivery && delivery.sheetStatus !== 'ok') {
      debugLog('Enregistrement Google Sheets non confirmé.', delivery.sheetError || '');
    }
  }

  function pushLeadEvents(data) {
    window.dataLayer = window.dataLayer || [];
    var eventData = {
      event: 'formulaire_lead',
      form_id: formConfig.formId,
      lead_type: data.reponse_3 === 'Oui' ? 'micro_entrepreneur' : 'standard'
    };
    if (analyticsGranted()) {
      if (parentLandingUrlReceived) eventData.page_url = clean(trackedPageUrl || entryUrl, 1000);
      eventData.categorie = clean(data.categorie || '', 200);
      ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id',
        'utm_category', 'utm_user', 'ltm_source', 'ltm_category', 'ltm_typ', 'ltm_user'].forEach(function (key) {
        if (data[key]) eventData[key] = data[key];
      });
    }
    if (marketingGranted()) {
      ['gclid', 'msclkid', 'fbclid'].forEach(function (key) {
        if (data[key]) eventData[key] = data[key];
      });
    }
    window.dataLayer.push(eventData);
  }

  function submitLead() {
    if (sending) return;
    if (honeypot && clean(honeypot.value)) {
      debugLog('Honeypot rempli; envoi ignoré.');
      showDone(null);
      return;
    }
    sending = true;
    updateNextButton();
    if (formError) formError.textContent = '';

    var data = buildCrmData();
    var recapField = form.querySelector('[name="autre_info_fj"]');
    if (recapField) recapField.value = data.autre_info_fj;
    debugLog('Payload CRM/Sheets préparé.', { formId: formConfig.formId, categorie: data.categorie });
    // Déclencher l’événement de conversion dès la soumission valide, comme demandé.
    pushLeadEvents(data);

    var crmDelivery = sendCrm(data).then(function (result) {
      return { ok: true, result: result };
    }).catch(function (error) {
      return { ok: false, error: error };
    });
    var sheetDelivery = sendToGoogleSheets(data).then(function (result) {
      return { ok: true, result: result };
    }).catch(function (error) {
      return { ok: false, error: error };
    });

    Promise.all([crmDelivery, sheetDelivery]).then(function (results) {
      var crm = results[0];
      var sheet = results[1];
      var delivery = {
        crmStatus: crm.ok ? crm.result.state : 'error',
        sheetStatus: sheet.ok ? sheet.result.state : 'error',
        confirmed: sheet.ok && sheet.result.confirmed === true,
        crmError: crm.ok ? null : crm.error,
        sheetError: sheet.ok ? null : sheet.error
      };
      if (!crm.ok) debugLog('Échec du transport CRM.', crm.error);
      if (!sheet.ok) debugLog('Échec du transport Google Sheets.', sheet.error);

      if (crm.ok || sheet.ok) {
        showDone(delivery);
      } else {
        sending = false;
        updateNextButton();
        if (formError) formError.textContent = 'Nous n’avons pas pu transmettre votre demande. Vérifiez votre connexion puis réessayez.';
      }
    });
  }

  function buildCrmData() {
    var answers = summaryAndAnswers();
    var tracking = getTrackingPayload();
    var category = getCurrentUrlCategory() || textValue('categorie') || tracking.categorie || '';
    var campaignSource = tracking.ltm_source || tracking.utm_source || tracking.source || formConfig.source;
    var data = {
      nom: textValue('nom'),
      prenom: textValue('prenom'),
      mail: textValue('mail').toLowerCase(),
      telephone: currentPhone(),
      societe: textValue('societe'),
      code_postal: textValue('code_postal').replace(/\s+/g, ''),
      source: campaignSource,
      categorie: category,
      consentement: consentOk() ? 'oui' : 'non',
      telephone_verifie: smsVerified && verifiedPhone === currentPhone() ? 'oui' : 'non',
      question_1: 'Quels types d’assurances professionnelles recherchez-vous ?',
      reponse_1: answers.insurance.join(', '),
      question_2: 'Quelles garanties recherchez-vous ?',
      reponse_2: answers.mrp,
      question_3: 'Êtes-vous auto-entrepreneur ?',
      reponse_3: answers.auto,
      question_4: 'Quel est l’effectif de votre structure ?',
      reponse_4: answers.effectif,
      question_5: 'Protection sociale individuelle — Quels types de protection recherchez-vous ?',
      reponse_5: answers.psi,
      question_6: 'Protection sociale collective — Quels types de protection recherchez-vous ?',
      reponse_6: answers.psc,
      question_7: 'Quel est votre statut ?',
      reponse_7: answers.statut,
      question_8: 'Votre société existe-t-elle déjà ?',
      reponse_8: answers.companyState,
      autre_info_fj: answers.autreInfo
    };
    if (trackingGranted()) {
      ['user','utm_source','utm_medium','utm_campaign','utm_content','utm_term','utm_id',
        'utm_category','utm_user','ltm_source','ltm_category','ltm_typ','ltm_user'].forEach(function (key) {
        if (tracking[key]) data[key] = tracking[key];
      });
      if (analyticsGranted()) {
        if (parentLandingUrlReceived) data.page_url = clean(trackedPageUrl || entryUrl, 1000);
        data.page_referrer = safeReferrer();
        data.user_agent = clean(navigator.userAgent, 300);
        data.langue = clean(navigator.language || '', 20);
      }
    }
    if (marketingGranted()) {
      ['gclid', 'msclkid', 'fbclid'].forEach(function (key) {
        if (tracking[key]) data[key] = tracking[key];
      });
    }
    return data;
  }

  var honeypot = form.querySelector('input[name="website"]');
  if (!honeypot) {
    honeypot = document.createElement('input');
    honeypot.type = 'text';
    honeypot.name = 'website';
    honeypot.tabIndex = -1;
    honeypot.autocomplete = 'off';
    honeypot.setAttribute('aria-hidden', 'true');
    honeypot.className = 'hp-field';
    form.appendChild(honeypot);
  }

  form.addEventListener('change', syncConditions);
  syncConditions();
  initSmsVerification();

  next.addEventListener('click', function () {
    if (!validateStep()) return;
    if (current < steps.length - 1) {
      current += 1;
      render(true);
    } else {
      submitLead();
    }
  });

  prev.addEventListener('click', function () {
    if (current > 0) {
      current -= 1;
      render(true);
    }
  });

  form.addEventListener('keydown', function (event) {
    if (event.key !== 'Enter' || event.target.tagName === 'TEXTAREA') return;
    if (event.target.closest && event.target.closest('.sms-verification')) return;
    if (/^(checkbox|radio|button|submit)$/i.test(event.target.type || '')) return;
    event.preventDefault();
    if (event.target.name === 'sms-code') return;
    next.click();
  });

  form.addEventListener('change', function (event) {
    if (event.target && event.target.name === 'consentement') updateNextButton();
  });

  window.ubeproLead = Object.freeze({
    version: VERSION,
    config: {
      leadApiUrl: formConfig.leadApiUrl,
      leadApiMode: formConfig.leadApiMode,
      formId: formConfig.formId,
      smsApiUrl: formConfig.smsApiUrl,
      googleScriptUrl: formConfig.googleScriptUrl
    },
    preview: function () {
      var data = buildCrmData();
      return { payload: { formId: formConfig.formId, id: submissionId, data: data } };
    },
    googleSheetPreview: function () {
      return buildSheetData(buildCrmData());
    },
    tracking: window.ubeproTracking.inspect
  });

  render(false);
})();

} catch (e) { console.error("[lp2site] script 0 en échec :", e); }
