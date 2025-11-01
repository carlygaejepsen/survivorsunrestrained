(function () {
    'use strict';

    const config = window.suResourceBrowser || {};
    const datasetBaseUrl = config.datasetsBaseUrl ? config.datasetsBaseUrl.replace(/\/$/, '') : '';
    const availableStates = Array.isArray(config.states) ? config.states : [];
    const labels = config.i18n || {};
    const cacheBuster = typeof config.cacheBuster === 'string' && config.cacheBuster.length
        ? config.cacheBuster
        : '';

    let rawDataset = [];
    let currentDataset = [];
    let currentStateCode = null;

    function getElement(id) {
        return document.getElementById(id);
    }

    function updateInterfaceLabels() {
        const stateLabel = document.querySelector('label[for="state-selector"]');
        const searchLabel = document.querySelector('label[for="search-input"]');
        const stateSelector = getElement('state-selector');

        if (stateLabel && labels.stateLabel) {
            stateLabel.textContent = labels.stateLabel;
        }

        if (searchLabel && labels.searchLabel) {
            searchLabel.textContent = labels.searchLabel;
        }

        if (stateSelector && labels.chooseState) {
            const placeholderOption = stateSelector.querySelector('option[value=""]');
            if (placeholderOption) {
                placeholderOption.textContent = labels.chooseState;
            }
        }
    }

    function populateStateSelector() {
        const stateSelector = getElement('state-selector');
        if (!stateSelector) {
            return;
        }

        if (!availableStates.length) {
            stateSelector.disabled = true;
            const placeholderOption = stateSelector.querySelector('option[value=""]');
            if (placeholderOption) {
                placeholderOption.textContent = labels.noDatasets || 'No datasets found';
            }
            return;
        }

        stateSelector.disabled = false;
        const fragment = document.createDocumentFragment();
        availableStates.forEach(function (code) {
            const option = document.createElement('option');
            option.value = code.toLowerCase();
            option.textContent = code.toUpperCase();
            fragment.appendChild(option);
        });

        stateSelector.appendChild(fragment);
    }

    async function fetchDatasetByState(stateCode) {
        if (!stateCode || !datasetBaseUrl) {
            return { data: null, url: null, error: 'Dataset location not configured.' };
        }

        const basePath = datasetBaseUrl + '/' + stateCode.toLowerCase() + '_food_pantries_202510.json';
        const url = cacheBuster ? basePath + '?ver=' + encodeURIComponent(cacheBuster) : basePath;

        try {
            const response = await fetch(url, { cache: 'no-cache' });
            if (!response.ok) {
                const errorText = await response.text();
                return { error: errorText || 'Dataset failed to load.', url: url };
            }

            const data = await response.json();
            return { data: data, url: url };
        } catch (error) {
            return { error: error.message, url: url };
        }
    }

    function createDetailRow(label, value) {
        if (!value) {
            return '';
        }

        var displayValue = String(value).replace(/\r?\n/g, '<br>');
        return (
            '<div class="py-2 border-b border-gray-100 flex flex-col sm:flex-row sm:items-baseline">' +
            '<span class="detail-label w-full sm:w-1/3">' + label + ':</span>' +
            '<span class="detail-value w-full sm:w-2/3">' + displayValue + '</span>' +
            '</div>'
        );
    }

    function filterAndRenderList(searchTerm) {
        const searchInput = getElement('search-input');
        const term = (searchTerm || '').toLowerCase().trim();

        if (!term) {
            currentDataset = rawDataset.slice();
        } else {
            currentDataset = rawDataset.filter(function (item) {
                return (
                    (item.name && item.name.toLowerCase().includes(term)) ||
                    (item.city && item.city.toLowerCase().includes(term))
                );
            });
        }

        renderListView(currentDataset, currentStateCode, term);

        if (searchInput) {
            searchInput.disabled = rawDataset.length === 0;
            searchInput.value = searchTerm || '';
        }
    }

    function renderListView(dataset, stateCode, filterTerm) {
        const container = getElement('pantry-card-container');
        if (!container) {
            return;
        }

        if (!dataset.length && rawDataset.length > 0) {
            container.innerHTML =
                '<div class="su-card p-8 rounded-xl text-center border-l-4 border-yellow-500">' +
                '<h2 class="text-2xl font-bold text-yellow-600 mb-2">No Matches Found</h2>' +
                '<p class="text-gray-600">No food pantries matched the search term <strong>"' +
                (filterTerm || '') +
                '"</strong> in ' +
                stateCode.toUpperCase() +
                '. Try a different term.</p>' +
                '</div>';
            return;
        }

        if (!dataset.length && !rawDataset.length) {
            container.innerHTML =
                '<div class="su-card p-8 rounded-xl text-center border-l-4 border-yellow-500">' +
                '<h2 class="text-2xl font-bold text-yellow-600 mb-2">No Records Found</h2>' +
                '<p class="text-gray-600">The dataset loaded successfully, but contained no food pantry records for ' +
                stateCode.toUpperCase() +
                '.</p>' +
                '</div>';
            return;
        }

        const listHtml = dataset
            .map(function (item) {
                return (
                    '<li class="p-4 border-b border-gray-200 hover:bg-gray-50 cursor-pointer transition duration-150 ease-in-out" data-id="' +
                    item.id +
                    '">' +
                    '<h3 class="text-xl font-semibold text-primary">' + item.name + '</h3>' +
                    '<p class="text-sm text-gray-600">' + item.city + ', ' + item.state + '</p>' +
                    '</li>'
                );
            })
            .join('');

        container.innerHTML =
            '<div class="su-card p-6 rounded-xl">' +
            '<h2 class="text-2xl font-bold text-gray-800 mb-4">Food Pantries in ' +
            stateCode.toUpperCase() +
            ' (' + dataset.length + ' of ' + rawDataset.length + ' shown)</h2>' +
            '<ul class="divide-y divide-gray-100" id="pantry-list">' +
            listHtml +
            '</ul>' +
            '</div>';
    }

    function renderDetailView(record) {
        const container = getElement('pantry-card-container');
        if (!container) {
            return;
        }

        const emailLink = record.email
            ? '<a href="mailto:' + record.email + '" class="text-primary hover:text-green-700 underline">' + record.email + '</a>'
            : 'N/A';
        const websiteLink = record.website
            ? '<a href="' + record.website + '" target="_blank" rel="noopener" class="text-primary hover:text-green-700 underline">' + record.website + '</a>'
            : 'N/A';
        const phoneLink = record.phone
            ? '<a href="tel:' + (record.phone || '').replace(/[^0-9]/g, '') + '" class="text-primary hover:text-green-700 underline">' + record.phone + '</a>'
            : 'N/A';

        container.innerHTML =
            '<div class="su-card p-6 sm:p-8 rounded-xl transition-all duration-300">' +
            '<button type="button" class="mb-4 text-sm text-primary hover:text-green-700 font-medium flex items-center p-2 rounded-lg transition duration-150 ease-in-out" id="back-to-list">' +
            '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18" />' +
            '</svg>' +
            'Back to List' +
            '</button>' +
            '<div class="flex items-center justify-between mb-6 border-b pb-4 border-primary/20">' +
            '<h2 class="text-3xl font-extrabold text-gray-900">' + record.name + '</h2>' +
            '<span class="bg-primary text-white text-sm font-semibold px-3 py-1 rounded-full shadow-md">ID: ' + record.id + '</span>' +
            '</div>' +
            '<div class="divide-y divide-gray-200">' +
            '<h3 class="text-xl font-semibold text-gray-700 mt-4 mb-2 pt-4">Location</h3>' +
            createDetailRow('Street Address', record.address) +
            createDetailRow('City, State, Zip', record.city + ', ' + record.state + ' ' + record.zip) +
            createDetailRow('Geocoded Address', record.geocoded_address) +
            '<div class="py-2 border-b border-gray-100 flex flex-col sm:flex-row sm:items-baseline">' +
            '<span class="detail-label w-full sm:w-1/3">Map Coordinates:</span>' +
            '<span class="detail-value w-full sm:w-2/3">' + record.latitude + ', ' + record.longitude + '</span>' +
            '</div>' +
            '<h3 class="text-xl font-semibold text-gray-700 mt-4 mb-2 pt-4">Operation</h3>' +
            createDetailRow('Hours/Volunteering', record.hours) +
            createDetailRow('Description', record.description) +
            createDetailRow('Requirements', record.requirements || 'None listed') +
            '<h3 class="text-xl font-semibold text-gray-700 mt-4 mb-2 pt-4">Contact</h3>' +
            createDetailRow('Phone', phoneLink) +
            createDetailRow('Email', emailLink) +
            createDetailRow('Website', websiteLink) +
            '<p class="text-xs text-gray-400 mt-6 pt-4 text-right">Scraped At: ' + new Date(record.scraped_at).toLocaleString() + '</p>' +
            '</div>' +
            '</div>';

        const backButton = getElement('back-to-list');
        if (backButton) {
            backButton.addEventListener('click', goBackToList);
        }
    }

    function handleListClick(event) {
        const target = event.target.closest('li[data-id]');
        if (!target) {
            return;
        }

        const id = parseInt(target.getAttribute('data-id'), 10);
        const record = currentDataset.find(function (item) {
            return item.id === id;
        });

        if (record) {
            renderDetailView(record);
        }
    }

    function goBackToList() {
        const searchInput = getElement('search-input');
        if (searchInput) {
            filterAndRenderList(searchInput.value);
        }
    }

    async function handleStateChange() {
        const stateSelector = getElement('state-selector');
        const searchInput = getElement('search-input');
        const pathDisplay = getElement('filepath-display');
        const container = getElement('pantry-card-container');

        if (!stateSelector || !searchInput || !container) {
            return;
        }

        const selectedState = stateSelector.value;
        if (!selectedState) {
            container.innerHTML =
                '<div class="su-card p-6 rounded-xl text-center"><p class="text-xl text-primary su-pulse">Select a State to load data...</p></div>';
            pathDisplay.textContent = '';
            searchInput.disabled = true;
            searchInput.value = '';
            rawDataset = [];
            currentDataset = [];
            currentStateCode = null;
            return;
        }

        pathDisplay.textContent = 'Path: Loading data for ' + selectedState.toUpperCase() + '...';
        container.innerHTML = '<div class="su-card p-6 rounded-xl text-center"><p class="text-xl text-primary su-pulse">Loading dataset for ' + selectedState.toUpperCase() + '...</p></div>';

        searchInput.disabled = true;
        searchInput.value = '';
        rawDataset = [];

        const result = await fetchDatasetByState(selectedState);
        if (pathDisplay && result.url) {
            pathDisplay.textContent = 'Fetching path: ' + result.url;
        }

        if (result.error) {
            container.innerHTML =
                '<div class="su-card p-8 rounded-xl text-center border-l-4 border-red-500">' +
                '<h2 class="text-2xl font-bold text-red-600 mb-2">Error Loading Data</h2>' +
                '<p class="text-gray-600">' + result.error + '</p>' +
                '<p class="text-sm mt-4 text-gray-400">Please check if the file path is correct.</p>' +
                '</div>';
            return;
        }

        rawDataset = Array.isArray(result.data) ? result.data : [];
        currentStateCode = selectedState;
        filterAndRenderList('');
    }

    function attachEventListeners() {
        const stateSelector = getElement('state-selector');
        const searchInput = getElement('search-input');
        const container = getElement('pantry-card-container');

        if (stateSelector) {
            stateSelector.addEventListener('change', handleStateChange);
        }

        if (searchInput) {
            searchInput.addEventListener('input', function (event) {
                if (rawDataset.length > 0) {
                    filterAndRenderList(event.target.value);
                }
            });
        }

        if (container) {
            container.addEventListener('click', handleListClick);
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        updateInterfaceLabels();
        populateStateSelector();
        attachEventListeners();
    });
})();
