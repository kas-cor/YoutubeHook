// ==UserScript==
// @name         YoutubeHook
// @namespace    http://tampermonkey.net/
// @version      0.1.0
// @description  YouTube webhook tracker - sends watched video IDs to webhook
// @author       kas-cor
// @match        https://www.youtube.com/*
// @match        https://youtube.com/*
// @icon         https://www.google.com/s2/favicons?sz=64&domain=youtube.com
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @grant        GM_addStyle
// @grant        GM_xmlhttpRequest
// @connect      *
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        debug: true,
        version: '0.1.0',
        storageKey: 'sent_video_ids',
        webhookUrlKey: 'webhook_url'
    };

    // Logger utility
    const logger = {
        log: (...args) => CONFIG.debug && console.log('[YoutubeHook]', ...args),
        error: (...args) => console.error('[YoutubeHook]', ...args),
        warn: (...args) => console.warn('[YoutubeHook]', ...args)
    };

    // Settings management
    const settings = {
        getWebhookUrl: () => GM_getValue(CONFIG.webhookUrlKey, ''),
        setWebhookUrl: (url) => GM_setValue(CONFIG.webhookUrlKey, url),
        getSentIds: () => {
            const data = GM_getValue(CONFIG.storageKey, '[]');
            try {
                return JSON.parse(data);
            } catch (e) {
                return [];
            }
        },
        addSentId: (id) => {
            const ids = settings.getSentIds();
            if (!ids.includes(id)) {
                ids.push(id);
                GM_setValue(CONFIG.storageKey, JSON.stringify(ids));
            }
        },
        clearSentIds: () => GM_deleteValue(CONFIG.storageKey),
        isIdSent: (id) => settings.getSentIds().includes(id)
    };

    // Extract video ID from URL
    function extractVideoId(url) {
        const match = url.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
        return match ? match[1] : null;
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
            title: document.title.replace(' - YouTube', '').trim(),
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
            .replace(/{timestamp}/g, encodeURIComponent(videoInfo.timestamp))
            .replace(/%VIDEO_ID%/g, encodeURIComponent(videoInfo.videoId))
            .replace(/\{\{videoId\}\}/g, encodeURIComponent(videoInfo.videoId));

        logger.log(`Sending video ${videoId} to webhook: ${finalUrl}`);

        GM_xmlhttpRequest({
            method: 'GET',
            url: finalUrl,
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
                settings.setWebhookUrl(newUrl.trim());
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
        
        // Monitor URL changes (YouTube is SPA)
        let lastUrl = location.href;
        const urlObserver = new MutationObserver(() => {
            if (location.href !== lastUrl) {
                lastUrl = location.href;
                handleUrlChange();
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
