import "jquery-ui-dist/jquery-ui.min.js";
import "jquery-ui-dist/jquery-ui.min.css";
import "popper.js";
import "bootstrap";
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/dist/css/bootstrap-reboot.min.css";
import "dropzone/dist/min/basic.min.css";
import "dropzone/dist/min/dropzone.min.css";
// import '@recogito/annotorious/dist/annotorious.min.css';
import "lodash";
import "@fortawesome/fontawesome-free/css/all.min.css";
import "moment-timezone/builds/moment-timezone-with-data-10-year-range.min.js";
import "@escriptorium/virtual-keyboard/dist-lib/content.js";
import "bootstrap-select/dist/css/bootstrap-select.css";
import Vue from "vue";
import jquery from "jquery";
import Dropzone from "dropzone";
import moment from "moment/moment";
import paper from "paper";
import UndoManager from "undo-manager";
import Sortable from "sortablejs/Sortable";
import ReconnectingWebSocket from "reconnectingwebsocket";
import Cookies from "js-cookie";
import * as Diff from "diff";
import math from "mathjs/dist/math.min";
import BootstrapSelect from "bootstrap-select/dist/js/bootstrap-select";

// Vue needs to be explicitly set on window, as some legacy editor modules
// reference Vue globally.
window.Vue = Vue;

// JQuery needs to be explicitly set on window, as it's used at boot time
// by various scripts
window.jQuery = window.$ = jquery;

// Dropzone needs to be explicitly set on window, as it's modified at boot time
// by image-cards.js
window.Dropzone = Dropzone;

// moment needs to be explicitly set on window, as it's used at boot time
// by trans_modal.js
window.moment = moment;

// Paper needs to be explicitly set on window, as it's used at boot time
// by baseline.editor.js
window.paper = paper;

// Undo-manager needs to be explicitly set on window, as it's used at boot time
// by seg_panel.js
window.UndoManager = UndoManager;

// Sortable needs to be explicitly set on window, as it's used at boot time
// by diplo_panel.js
window.Sortable = Sortable;

// ReconnectingWebSocket needs to be explicitly set on window, as it's used at boot time
// by messages.js
window.ReconnectingWebSocket = ReconnectingWebSocket;

// Js-cookie needs to be explicitly set on window, as it's used at boot time
// by ajax.js
window.Cookies = Cookies;

// Diff needs to be explicitly set on window, as it's used at boot time
// by various scripts
window.Diff = Diff;

// Mathjs needs to be explicitly set on window, as it's used at boot time
// by baseline.editor.js
window.math = math;

//Bootstrap select
window.BootstrapSelect = BootstrapSelect;
