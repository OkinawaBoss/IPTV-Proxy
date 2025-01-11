let parsedChannels = [];
let parsedEPG = {};
let filteredUrls = []; // To store URLs of filtered channels
let selectedUrls = new Set(); // Use a Set to efficiently store unique URLs

/**
 * Utility: Debugging log wrapper
 */
function debugLog(message, data = null) {
  if (data) {
    console.log(`[DEBUG] ${message}`, data);
  } else {
    console.log(`[DEBUG] ${message}`);
  }
}

/**
 * Toggle "Select All" checkboxes in the DataTable
 */
function toggleSelectAll() {
  const table = $("#dataTable").DataTable();
  const visibleRows = table.rows({ page: "all" }).nodes();
  const allSelected = $(visibleRows).find(".select-icon[data-selected='false']").length === 0;

  $(visibleRows)
    .find(".select-icon")
    .each(function () {
      const isSelected = $(this).attr("data-selected") === "true";
      $(this).attr("data-selected", allSelected ? "false" : "true")
             .toggleClass("selected", !allSelected)
             .toggleClass("unselected", allSelected)
             .html(allSelected ? "<span style='color: green;'>+</span>" : "<span style='color: red;'>-</span>");

      const url = $(this).data("url");
      if (allSelected) {
        selectedUrls.delete(url);
      } else {
        selectedUrls.add(url);
      }
    });

  debugLog(allSelected ? "All visible checkboxes deselected." : "All visible checkboxes selected.");
}

// Attach event listener to the "Select All" button
//document.getElementById("selectAllButton").addEventListener("click", toggleSelectAll);

/**
 * Dynamically populate checkboxes for filtering by group
 */
function populateGroupCheckboxes() {
  if (!parsedChannels.length) {
    console.warn("[WARN] No channels available to populate group checkboxes.");
    return;
  }

  const groups = [...new Set(parsedChannels.map((channel) => channel.group).filter(Boolean))]; // Get unique, non-empty groups
  const container = document.getElementById("groupCheckboxes");

  if (!groups.length) {
    console.warn("[WARN] No groups found in the parsed channels.");
    return;
  }

  groups.forEach((group) => {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = group;
    checkbox.id = `group-${group}`;
    checkbox.classList.add("group-filter");

    const label = document.createElement("label");
    label.htmlFor = `group-${group}`;
    label.textContent = group;

    container.appendChild(checkbox);
    container.appendChild(label);
    container.appendChild(document.createElement("br")); // Line break
  });

  // Add event listener to filter table when checkboxes change
  document.querySelectorAll(".group-filter").forEach((checkbox) => {
    checkbox.addEventListener("change", filterDataTableByGroup);
  });

  debugLog("Group checkboxes populated successfully.", groups);
}

/**
 * Filter the DataTable based on selected groups
 */
function filterDataTableByGroup() {
  const selectedGroups = Array.from(
    document.querySelectorAll(".group-filter:checked")
  ).map((checkbox) => checkbox.value);

  if (selectedGroups.length === 0) {
    initializeDataTable(); // Show all channels if no groups are selected
  } else {
    const filteredChannels = parsedChannels.filter((channel) =>
      selectedGroups.includes(channel.group)
    );
    initializeDataTable(filteredChannels); // Initialize DataTable with filtered channels
  }
}


/**
 * Check if a local file exists
 */
function checkFileExists(filePath) {
  debugLog(`Checking if file exists: ${filePath}`);
  return fetch(filePath, { method: "HEAD" })
    .then((response) => {
      debugLog(`File exists check for ${filePath}: ${response.ok}`);
      return response.ok;
    })
    .catch((error) => {
      console.error(`[ERROR] Error checking file existence: ${filePath}`, error);
      return false;
    });
}

/**
 * Load IPTV file from local storage or server
 */
async function loadMasterM3U() {
  debugLog("Starting to load Master M3U...");
  const localFilePath = "./Fresh/unfiltered.m3u";

  const fileExists = await checkFileExists(localFilePath);
  let data;
  if (fileExists) {
    debugLog("IPTV file exists locally. Loading from local storage...");
    data = await fetch(localFilePath).then(r => r.text());
  } else {
    // Fallback if not local
    debugLog("IPTV file not found locally. Fetching from server...");
    data = await fetch("/playlist.m3u").then(r => r.text());
  }

  if (!data.trim()) {
    console.error("[ERROR] unfiltered.m3u is empty. Stopping initialization.");
    throw new Error("No data in unfiltered.m3u");
  }

  // Parse & filter
  const rawChannels = parseM3U(data);
  parsedChannels = filterChannels(rawChannels);  // remove excluded groups
  debugLog("Parsed channels", parsedChannels);
}


/**
 * Load EPG file from local storage or server
 */
async function loadEPG() {
  debugLog("Starting to load EPG...");
  const localEPGPath = "./Fresh/unfiltered.xml";

  const fileExists = await checkFileExists(localEPGPath);
  let data = "";
  if (fileExists) {
    debugLog("EPG file exists locally. Loading from local storage...");
    data = await fetch(localEPGPath).then(r => r.text());
  } else {
    // Fallback if not local
    debugLog("EPG file not found locally. Fetching from server...");
    data = await fetch("/epg.xml").then(r => r.text());
  }

  if (!data.trim()) {
    console.warn("[WARN] Empty EPG data. Proceeding without EPG.");
    parsedEPG = {};
    return;
  }

  // Parse EPG and match
  debugLog("EPG data loaded successfully.");
  parsedEPG = parseEPG(data);
  debugLog("Parsed EPG data", parsedEPG);

  matchEPGToChannels();
  debugLog("EPG matched to channels.");
}


/**
 * Parse M3U data into an array of channels
 */
function parseM3U(data) {
  if (!data || !data.trim()) {
    console.warn("[WARN] Empty M3U data provided.");
    return [];
  }

  const channels = [];
  let tempInfo = null;

  data.trim().split("\n").forEach((line) => {
    line = line.trim();
    if (!line || line === "#EXTM3U") return;

    if (line.startsWith("#EXTINF")) {
      tempInfo = line;
    } else if (tempInfo && line.startsWith("http")) {
      const tvgNameMatch = /tvg-name="([^"]*?)"/.exec(tempInfo);
      const tvgLogoMatch = /tvg-logo="([^"]*?)"/.exec(tempInfo);
      const groupMatch = /group-title="([^"]*?)"/.exec(tempInfo);
      const tvgIDMatch = /tvg-ID="([^"]*?)"/.exec(tempInfo);

      channels.push({
        tvgID: tvgIDMatch ? tvgIDMatch[1] : "",
        tvgName: tvgNameMatch ? tvgNameMatch[1] : "",
        tvgLogo: tvgLogoMatch ? tvgLogoMatch[1] : "",
        group: groupMatch ? groupMatch[1] : "",
        url: line,
        epg: [],
      });

      tempInfo = null;
    }
  });

  console.log(`[INFO] Parsed ${channels.length} channels from M3U.`);
  return channels;
}





/**
 * Parse EPG data into an object
 */
function parseEPG(data) {
  debugLog("Parsing EPG data...");
  if (!data.trim()) return {};
  const programs = {};
  const parser = new DOMParser();
  const xmlDoc = parser.parseFromString(data, "application/xml");

  xmlDoc.querySelectorAll("programme").forEach((programme) => {
    const channel = programme.getAttribute("channel");
    const start = programme.getAttribute("start");
    const stop = programme.getAttribute("stop");
    const title = programme.querySelector("title")?.textContent || "No title";
    if (!programs[channel]) programs[channel] = [];
    programs[channel].push({ start, stop, title });
  });

  debugLog("EPG parsed programs", programs);
  return programs;
}

/**
 * Match EPG data to parsed channels
 */
function matchEPGToChannels() {
  debugLog("Matching EPG to channels...");
  parsedChannels.forEach((channel) => {
    channel.epg = parsedEPG[channel.tvgName] || []; // Default to empty array if no EPG data
  });
  debugLog("EPG matched to channels", parsedChannels);
}

async function fetchM3UFile(filePath) {
  const fileExists = await checkFileExists(filePath);
  if (!fileExists) {
    debugLog(`[WARN] M3U file not found: ${filePath}`);
    return "";
  }
  const data = await fetch(filePath).then((res) => res.text());
  return data || "";
}


/**
 * Initialize DataTable
 */
async function initializeDataTable(channels = []) {
  if (!document.getElementById("dataTable")) {
    console.error("[ERROR] #dataTable element not found in the DOM.");
    return;
  }

  if (!Array.isArray(channels) || channels.length === 0) {
    console.warn("[WARN] No channels provided for DataTable initialization.");
    return;
  }

  // Load both filtered.m3u and unfiltered.m3u into memory
  const filteredM3U = await fetchM3UFile("./Fresh/filtered.m3u");
  const unfilteredM3U = await fetchM3UFile("./Fresh/unfiltered.m3u");

  // Parse M3U files into arrays of channels
  const filteredChannels = parseM3U(filteredM3U);
  const unfilteredChannels = parseM3U(unfilteredM3U);

  const urlToTvgID = new Map();
  [...filteredChannels, ...unfilteredChannels].forEach((channel) => {
    const url = channel.url.trim();
    const tvgID = channel.tvgID?.trim() || "";
    if (url) {
      if (!urlToTvgID.has(url)) {
        urlToTvgID.set(url, new Set());
      }
      urlToTvgID.get(url).add(tvgID); // Add tvg-ID to the set for this URL
    }
  });

  // Check if tvg-ID exists in the set
  const hasTvgID = (url) => {
    const tvgIDs = urlToTvgID.get(url.trim());
    if (tvgIDs && tvgIDs.size > 0) {
      return [...tvgIDs].some((tvgID) => tvgID !== ""); // Ensure there's at least one non-empty tvg-ID
    }
    return false;
  };

  // Prepare table data
  const tableData = channels.map((ch) => [
    `<div class="select-icon" data-selected="${selectedUrls.has(ch.url) ? "selected" : "unselected"}" data-url="${ch.url}">
       ${selectedUrls.has(ch.url) ? "<span>-</span>" : "<span>+</span>"}
     </div>`,
    ch.tvgLogo
      ? `<img class="logo lazy-logo" data-src="${ch.tvgLogo}" alt="Logo" width="80">`
      : "No Logo",
    ch.tvgName || "Unknown",
    ch.group || "Unknown",
    ch.url || "N/A",
    hasTvgID(ch.url) // Pass ch.url here
      ? `<span style="color: green; font-weight: bold;">✔️</span>` // Show checkmark if tvg-ID exists
      : `<span style="color: black; font-weight: bold;">✖️</span>` // Show X if no tvg-ID
  ]);

  // Destroy any existing table to avoid the error
  if ($.fn.DataTable.isDataTable("#dataTable")) {
    $("#dataTable").DataTable().clear().destroy();
  }

  // Initialize DataTable
  const table = $("#dataTable").DataTable({
    data: tableData,
    columns: [
      { title: "Select", width: "5%" },
      { title: "Logo", width: "10%" },
      { title: "TVG Name", width: "30%" },
      { title: "Group", width: "20%" },
      { title: "Stream URL", width: "25%" },
      { title: "EPG", width: "10%" },
    ],
    responsive: true,
    pageLength: 20,
    language: { emptyTable: "No channels to display" },
    createdRow: function (row, data, dataIndex) {
      const selectIcon = $("td:first-child .select-icon", row);
      selectIcon.on("click", function () {
        const isSelected = $(this).attr("data-selected") === "selected";
        const newState = isSelected ? "unselected" : "selected";
        $(this).attr("data-selected", newState);

        const url = $(this).data("url");
        if (newState === "selected") {
          selectedUrls.add(url);
          $(this).html("<span>-</span>");
        } else {
          selectedUrls.delete(url);
          $(this).html("<span>+</span>");
        }
      });
    },
  });













  // After each table draw (pagination, sorting, etc.), load visible logos
  $("#dataTable").on("draw.dt", function () {
    loadVisibleLogosForCurrentPage(table);
  });

  // Load logos for the first page now
  loadVisibleLogosForCurrentPage(table);

  console.log("[INFO] DataTable initialized successfully.");
}





    $("#refreshEPGBtn").on("click", function() {
      fetch("/epg/refresh", {method: "POST"})
      .then(r => r.json())
      .then(data => {
        console.log("EPG refresh response:", data);
        alert("EPG refreshed! Check logs for details.");
      })
      .catch(err => console.error("EPG refresh failed:", err));
    });

    // Refresh M3U
    $("#refreshM3UBtn").on("click", function() {
      fetch("/m3u/refresh", {method: "POST"})
      .then(r => r.json())
      .then(data => {
        console.log("M3U refresh response:", data);
        alert("M3U refreshed! Check logs for details.");
        // Possibly reload the page or re-invoke loadMasterM3U() to reflect changes
        location.reload();
      })
      .catch(err => console.error("M3U refresh failed:", err));
    });

    // Save Filter
    $("#saveFilteredBtn").on("click", function() {
      saveFiltered();
    });
/**
 * Load visible logos lazily for the current DataTable page
 */
function loadVisibleLogosForCurrentPage() {
  const table = $("#dataTable").DataTable();
  const rows = table.rows({ page: "current" }).nodes();

  $(rows)
    .find(".lazy-logo[data-src]")
    .each(function () {
      const logoUrl = $(this).attr("data-src");
      // Assign src only now
      $(this).attr("src", logoUrl);
      // Remove data-src so we don’t double-load it
      $(this).removeAttr("data-src");
    });
}

/**
 * Load filtered playlist
 */
async function loadFiltered() {
  debugLog("Loading filtered.m3u...");
  const filteredPath = "./Fresh/filtered.m3u";
  const fileExists = await checkFileExists(filteredPath);

  if (!fileExists) {
    debugLog("[WARN] No filtered.m3u file found. Using empty selection.");
    selectedUrls.clear();
    return;
  }

  // Parse the filtered file
  const data = await fetch(filteredPath).then(r => r.text());
  if (!data.trim()) {
    debugLog("[WARN] filtered.m3u is empty. Using empty selection.");
    selectedUrls.clear();
    return;
  }

  // Parse channels from filtered and store their URLs
  const filteredChannels = parseM3U(data);
  selectedUrls = new Set(filteredChannels.map(ch => ch.url));
  debugLog("Filtered channels loaded successfully.", filteredChannels);
}



/**
 * Save filtered playlist to server
 */
function saveFiltered() {
  // 1) Filter the global parsedChannels so only those with a selected URL remain
  const filteredChannels = parsedChannels.filter(ch => selectedUrls.has(ch.url));

  // 2) Convert them to M3U lines, retaining tvg-ID if present
  //    We do NOT re-normalize anything. We keep original tvgName, tvgID, etc.
  let lines = [];
  lines.push("#EXTM3U");
  filteredChannels.forEach(ch => {
    lines.push(
      `#EXTINF:-1 tvg-ID="${ch.tvgID || ''}" tvg-name="${ch.tvgName}" tvg-logo="${ch.tvgLogo}" group-title="${ch.group}",${ch.tvgName}`
    );
    lines.push(ch.url);
  });
  const m3uContent = lines.join("\n");

  // 3) POST it to the server
  fetch("/m3u/save_filtered_advanced", {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: m3uContent,
  })
    .then(response => {
      if (!response.ok) throw new Error("Failed to save filtered playlist");
      console.log("[INFO] Filtered playlist saved successfully with fuzzy matching!");
      alert("Filtered playlist saved!");
    })
    .catch(err => {
      console.error("[ERROR] Error saving filtered playlist:", err);
      alert("Failed to save filtered playlist. Check console for details.");
    });
  }


/**
 * Filter channels based on excluded groups
 */
function filterChannels(channels) {
  const excludedGroups = [
    "US NBC NETWORK",
    "USA Ultra 60FPS",
    "US ABC NETWORK",
    "US CBS NETWORK",
    "US CW NETWORK",
    "US ENTERTAINMENT NETWORK",
    "US FOX NETWORK",
    "US LOCAL",
    "US NEWS NETWORK",
    "US PBS NETWORK",
    "US SPORTS NETWORK",
    "USA METV NETWORK",
  ];

  return channels.filter((channel) => {
  //   // Exclude channels without a logo
  //   if (!channel.tvgLogo || channel.tvgLogo.trim() === "") return false;

  //   // Include channels matching specific naming patterns
  //   const seasonEpisodeRegex = /\bS\d{1,2}\s?E\d{1,4}\b/i;
  //   if (seasonEpisodeRegex.test(channel.tvgName)) return true;

  //   const yearRegex = /\b(19|20)\d{2}(_|-|\.|$|\s)/;
  //   if (yearRegex.test(channel.tvgName)) return true;

  //   // Exclude based on groups
  //   return !excludedGroups.includes(channel.group.toUpperCase());
        return channel;
  });
}

$(document).on("change", ".favorite-toggle", function () {
  const url = $(this).data("url");
  if (this.checked) {
    selectedUrls.add(url); // Add URL to the set
  } else {
    selectedUrls.delete(url); // Remove URL from the set
  }
});

// Attach event to "Save Filter" button
document.getElementById("saveFilteredBtn").addEventListener("click", saveFiltered);


// 1) Start everything in order, but don't re-call loadFiltered at the bottom again.
async function startApp() {
  try {
    // Step A: Load Master
    await loadMasterM3U();  // This sets parsedChannels in memory

    // Step B: Load EPG
    await loadEPG();        // This sets parsedEPG and merges into parsedChannels

    // Step C: Load user’s Filtered selection
    await loadFiltered();   // This sets selectedUrls from filtered.m3u

    // Step D: Now that all data is in memory (parsedChannels, parsedEPG, selectedUrls),
    //         initialize the DataTable exactly once:
    initializeDataTable(parsedChannels);

  } catch (err) {
    console.error("Critical error starting app:", err);
  }
}

// Then, near the bottom of app.js, just call:
$(document).ready(function() {
  startApp();
});


