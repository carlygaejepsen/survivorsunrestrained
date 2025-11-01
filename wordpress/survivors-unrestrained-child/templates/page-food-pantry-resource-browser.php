<?php
/**
 * Template Name: Food Pantry Resource Browser
 * Template Post Type: page
 */

global $post;

get_header();
?>

<main id="primary" class="site-main">
    <article id="post-<?php the_ID(); ?>" <?php post_class(); ?> aria-label="Food Pantry Resource Browser">
        <header class="entry-header screen-reader-text">
            <h1 class="entry-title"><?php the_title(); ?></h1>
        </header>

        <div id="su-resource-browser">
            <div class="su-container">
                <div class="mb-8">
                    <h2 class="text-3xl font-extrabold text-gray-900 mb-2">Food Pantry Resource Browser</h2>
                    <p class="text-gray-600">Select a state to view a list of available food pantry records. Click any item in the list to view its full details.</p>
                </div>

                <div class="mb-6">
                    <div class="flex flex-col sm:flex-row sm:gap-4 mb-2">
                        <div class="flex-grow sm:w-1/3 mb-4 sm:mb-0">
                            <label for="state-selector" class="block text-sm font-medium text-gray-700 mb-1">Select a State:</label>
                            <select id="state-selector" class="mt-1 block w-full py-2 px-3 border border-gray-300 bg-white rounded-lg shadow-sm focus:outline-none focus:ring-primary focus:border-primary sm:text-lg cursor-pointer transition duration-150 ease-in-out">
                                <option value="" disabled selected>Choose State</option>
                            </select>
                        </div>

                        <div class="flex-grow sm:w-2/3">
                            <label for="search-input" class="block text-sm font-medium text-gray-700 mb-1">Filter by Name or City:</label>
                            <input type="text" id="search-input" placeholder="Start typing to filter results..." disabled class="mt-1 block w-full py-2 px-3 border border-gray-300 bg-white rounded-lg shadow-sm focus:outline-none focus:ring-primary focus:border-primary sm:text-lg transition duration-150 ease-in-out">
                        </div>
                    </div>

                    <p id="filepath-display" class="mt-2 text-sm text-gray-500 font-mono break-all min-h-[1.5rem]"></p>
                </div>

                <div id="pantry-card-container">
                    <div id="initial-message" class="su-card p-6 rounded-xl text-center">
                        <p class="text-xl text-primary su-pulse">Select a State to load data...</p>
                    </div>
                </div>
            </div>
        </div>
    </article>
</main>

<?php
get_footer();
