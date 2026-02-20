// 1. process 폴리필 (가장 먼저 적용)
if (typeof global.process === 'undefined') {
    global.process = {
        env: { NODE_ENV: __DEV__ ? 'development' : 'production' },
        nextTick: (fn) => setTimeout(fn, 0),
        browser: true,
        cwd: () => '/',
    };
} else if (typeof global.process.env === 'undefined') {
    global.process.env = {};
}

// 2. Buffer 폴리필
if (typeof global.Buffer === 'undefined') {
    try {
        const bufferModule = require('buffer');
        global.Buffer = bufferModule.Buffer || bufferModule;
    } catch (e) {
        console.warn('[Polyfills] Failed to load buffer:', e);
    }
}

// 3. base-64 폴리필
if (typeof global.btoa === 'undefined') {
    try {
        const { encode } = require('base-64');
        global.btoa = encode;
    } catch (e) { }
}

if (typeof global.atob === 'undefined') {
    try {
        const { decode } = require('base-64');
        global.atob = decode;
    } catch (e) { }
}

// 4. TextEncoder & TextDecoder
if (typeof global.TextEncoder === 'undefined') {
    try {
        const encoding = require('text-encoding');
        global.TextEncoder = encoding.TextEncoder;
        global.TextDecoder = encoding.TextDecoder;
    } catch (e) {
        console.warn('[Polyfills] Failed to load text-encoding:', e);
    }
}

// 5. ReadableStream
if (typeof global.ReadableStream === 'undefined') {
    try {
        const streams = require('web-streams-polyfill');
        global.ReadableStream = streams.ReadableStream;
    } catch (e) {
        console.warn('[Polyfills] Failed to load web-streams-polyfill:', e);
    }
}

// 6. 기타 세이프 가드
if (typeof global.Atomics === 'undefined') {
    global.Atomics = {
        wait: () => 'not-supported',
        notify: () => 0,
    };
}

if (typeof global.getComputedStyle === 'undefined') {
    global.getComputedStyle = () => ({
        borderTopWidth: '0px',
        borderLeftWidth: '0px',
        borderRightWidth: '0px',
        borderBottomWidth: '0px',
        getPropertyValue: () => '',
    });
}

console.log('[Polyfills] Safe polyfills applied');
