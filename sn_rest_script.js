(function process(/*RESTAPIRequest*/ request, /*RESTAPIResponse*/ response) {
    var incidentsArray = [];

    var gr = new GlideRecord('incident');
    gr.addQuery('priority', '1');
    gr.addActiveQuery(); // Good practice: only get active incidents
    gr.orderBy('sys_created_on'); // Order by creation date for better organization
    gr.query();

    // Set a hard limit to prevent performance issues
    var limit = 200; 
    var count = 0;

    while (gr.next() && count < limit) {
        // Create a JavaScript OBJECT for each incident
        incidentsArray.push({
            number: gr.getValue('number'),
            short_description: gr.getValue('short_description'),
            state: gr.getDisplayValue('state'),
            sys_id: gr.getValue('sys_id'),
            description: gr.getValue('description'),
            opened_by: gr.getDisplayValue('opened_by'),
            created_on: gr.getValue('sys_created_on'),
            assignment_group: gr.getDisplayValue('assignment_group'),
            cmdb_ci: gr.getDisplayValue('cmdb_ci'),
            priority: gr.getDisplayValue('priority'),
            urgency: gr.getDisplayValue('urgency'),
            impact: gr.getDisplayValue('impact')
        });
        count++;
    }

    // Log the count for monitoring
    gs.info('High Priority Incidents API: Returning ' + incidentsArray.length + ' incidents');

    // Return the array directly wrapped in result object
    // This avoids the double-nesting issue
    response.setStatus(200);
    response.setContentType('application/json');
    response.setBody({
        result: incidentsArray,
        count: incidentsArray.length,
        timestamp: new GlideDateTime().toString()
    });

})(request, response);