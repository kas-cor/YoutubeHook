// ==UserScript==
// @name         YoutubeHook
// @namespace    http://tampermonkey.net/
// @version      0.2.0
// @description  YouTube webhook tracker - sends watched video IDs to webhook
// @author       kas-cor
// @match        https://www.youtube.com/*
// @match        https://youtube.com/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=youtube.com
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @grant        GM_xmlhttpRequest
// @connect      *
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        debug: true,
        version: '0.2.0',
        storageKey: 'sent_video_ids',
        webhookUrlKey: 'webhook_url',
        videoIdLength: 11,
        requestTimeout: 10000,
        debounceDelay: 300
    };

    // Logger utility
    const logger = {
        log: (...args) => CONFIG.debug && console.log('[YoutubeHook]', ...args),
        error: (...args) => console.error('[YoutubeHook]', ...args),
        warn: (...args) => console.warn('[YoutubeHook]', ...args)
    };

    // Settings management with in-memory cache
    const settings = {
        _cache: null,
        getWebhookUrl: () => GM_getValue(CONFIG.webhookUrlKey, ''),
        setWebhookUrl: (url) => GM_setValue(CONFIG.webhookUrlKey, url),
        _loadSentIds: () => {
            if (!settings._cache) {
                const data = GM_getValue(CONFIG.storageKey, '[]');
                try {
                    settings._cache = JSON.parse(data);
                } catch (e) {
                    settings._cache = [];
                }
            }
            return settings._cache;
        },
        getSentIds: () => settings._loadSentIds(),
        addSentId: (id) => {
            const ids = settings._loadSentIds();
            if (!ids.includes(id)) {
                ids.push(id);
                GM_setValue(CONFIG.storageKey, JSON.stringify(ids));
            }
        },
        clearSentIds: () => {
            settings._cache = null;
            GM_deleteValue(CONFIG.storageKey);
        },
        isIdSent: (id) => settings._loadSentIds().includes(id)
    };

    // Extract video title from page (falls back through multiple sources)
    function getVideoTitle() {
        const ogTitle = document.querySelector('meta[property="og:title"]');
        if (ogTitle) return ogTitle.content;
        const h1 = document.querySelector('h1');
        if (h1) return h1.textContent.trim();
        return document.title.replace(/ - YouTube$/, '').trim();
    }

    // Extract video ID from URL (supports /watch, /shorts, /embed, /live)
    function extractVideoId(url) {
        const patterns = [
            /[?&]v=([a-zA-Z0-9_-]{11})/,       // /watch?v=...
            /\/shorts\/([a-zA-Z0-9_-]{11})/,     // /shorts/...
            /\/embed\/([a-zA-Z0-9_-]{11})/,      // /embed/...
            /\/live\/([a-zA-Z0-9_-]{11})/        // /live/...
        ];
        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match) return match[1];
        }
        return null;
    }

    // Send video ID to webhook via GET request
    function sendToWebhook(videoId) {
        let webhookUrl = settings.getWebhookUrl();

        if (!webhookUrl) {
            logger.warn('Webhook URL not configured');
            return;
        }

        if (settings.isIdSent(videoId)) {
            logger.log(`Video ${videoId} already sent, skipping`);
            return;
        }

        // Gather video information
        const videoInfo = {
            videoId: videoId,
            id: videoId,
            title: getVideoTitle(),
            url: `https://www.youtube.com/watch?v=${videoId}`,
            timestamp: new Date().toISOString()
        };

        // Replace placeholders with actual values
        // Supported placeholders: {videoId}, {id}, {title}, {url}, {timestamp}
        let finalUrl = webhookUrl
            .replace(/{videoId}/g, encodeURIComponent(videoInfo.videoId))
            .replace(/{id}/g, encodeURIComponent(videoInfo.id))
            .replace(/{title}/g, encodeURIComponent(videoInfo.title))
            .replace(/{url}/g, encodeURIComponent(videoInfo.url))
            .replace(/{timestamp}/g, encodeURIComponent(videoInfo.timestamp));

        logger.log(`Sending video ${videoId} to webhook: ${finalUrl}`);

        GM_xmlhttpRequest({
            method: 'GET',
            url: finalUrl,
            timeout: CONFIG.requestTimeout,
            onload: function(response) {
                const status = response.status;
                if (status >= 200 && status < 300) {
                    logger.log(`Successfully sent video ${videoId} (HTTP ${status})`);
                    settings.addSentId(videoId);
                } else if (status >= 300 && status < 400) {
                    logger.log(`Redirect received for video ${videoId} (HTTP ${status}), treating as success`);
                    settings.addSentId(videoId);
                } else {
                    logger.error(`Failed to send video ${videoId} (HTTP ${status})`);
                }
            },
            onerror: function(error) {
                logger.error(`Request error for video ${videoId}:`, error);
            },
            ontimeout: function() {
                logger.error(`Request timed out for video ${videoId}`);
            }
        });
    }

    // Handle URL changes (SPA navigation)
    function handleUrlChange() {
        const videoId = extractVideoId(location.href);
        if (videoId) {
            logger.log(`Detected video page: ${videoId}`);
            sendToWebhook(videoId);
        }
    }

    // Validate webhook URL format
    function isValidUrl(string) {
        try {
            const url = new URL(string);
            return url.protocol === 'http:' || url.protocol === 'https:';
        } catch (_) {
            return false;
        }
    }

    // Main initialization
    function init() {
        logger.log('Initializing YoutubeHook v' + CONFIG.version);

        // Register Tampermonkey menu commands
        GM_registerMenuCommand('📝 Set Webhook URL', () => {
            const currentUrl = settings.getWebhookUrl();
            const defaultTemplate = 'https://example.com/hook?id={videoId}&title={title}';
            const placeholders = `Supported placeholders:
- {videoId} - video ID (URL encoded)
- {id} - video ID (URL encoded)
- {title} - video title (URL encoded)
- {url} - full YouTube URL (URL encoded)
- {timestamp} - ISO timestamp (URL encoded)`;
            const message = currentUrl
                ? `Enter webhook URL with placeholders:\n\n${placeholders}\n\nCurrent: ${currentUrl}`
                : `Enter webhook URL with placeholders:\n\nExample: ${defaultTemplate}\n\n${placeholders}`;
            const newUrl = prompt(message, currentUrl || defaultTemplate);
            if (newUrl !== null) {
                const trimmed = newUrl.trim();
                if (!trimmed || !isValidUrl(trimmed)) {
                    alert('Invalid URL. Please enter a valid HTTP or HTTPS URL.');
                    return;
                }
                settings.setWebhookUrl(trimmed);
                alert('Webhook URL saved');
            }
        });

        GM_registerMenuCommand('🗑️ Clear Sent History', () => {
            if (confirm('Clear all sent video IDs?')) {
                settings.clearSentIds();
                alert('History cleared');
            }
        });

        GM_registerMenuCommand('📊 Show Stats', () => {
            const count = settings.getSentIds().length;
            const webhook = settings.getWebhookUrl() || 'Not set';
            alert(`Webhook: ${webhook}\nSent videos: ${count}`);
        });

        // Monitor URL changes (YouTube is SPA) with debounce
        let lastUrl = location.href;
        let urlChangeTimer;
        const urlObserver = new MutationObserver(() => {
            if (location.href !== lastUrl) {
                clearTimeout(urlChangeTimer);
                urlChangeTimer = setTimeout(() => {
                    lastUrl = location.href;
                    handleUrlChange();
                }, CONFIG.debounceDelay);
            }
        });

        urlObserver.observe(document, { subtree: true, childList: true });

        // Initial check
        handleUrlChange();

        logger.log('YoutubeHook initialized successfully');
    }

    // Wait for document to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
