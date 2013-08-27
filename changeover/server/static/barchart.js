

function barChart(parentID, width, height, title, xLabel, yLabel, url, postData) {
    var margin = {top: 40, right: 20, bottom: 30, left: 40},
        chWidth = width - margin.left - margin.right,
        chHeight = height - margin.top - margin.bottom;

        var x = d3.scale.ordinal()
                  .rangeRoundBands([0, chWidth], .1);

        var y = d3.scale.linear()
                  .range([chHeight, 0]);

        var xAxis = d3.svg.axis()
                      .scale(x)
                      .orient("bottom");

        var yAxis = d3.svg.axis()
                      .scale(y)
                      .orient("left");

        var div = d3.select("body").append("div")   
                    .attr("class", "tooltip")               
                    .style("opacity", 0);

        var svg = d3.select(parentID).append("svg")
                    .attr("width", chWidth + margin.left + margin.right)
                    .attr("height", chHeight + margin.top + margin.bottom)
                    .append("g")
                    .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

        d3.json(url, function(error, data) {
            x.domain(data.map(function(d) { return d.bin; }));
            y.domain([0, d3.max(data, function(d) { return d.value; })]);

            svg.append("text")
               .attr("x", (chWidth / 2))
               .attr("y", 0 - (margin.top / 2))
               .attr("text-anchor", "middle")
               .style("font-size", "16px")
               .text(title);

            svg.append("g")
               .attr("class", "x axis")
               .attr("transform", "translate(0," + chHeight + ")")
               .call(xAxis)
               .append("text")
               .attr("class", "label")
               .attr("x", chWidth + 5)
               .attr("y", 18)
               .style("text-anchor", "end")
               .text(xLabel);

            svg.append("g")
               .attr("class", "y axis")
               .call(yAxis)
               .append("text")
               .attr("transform", "rotate(-90)")
               .attr("y", 6)
               .attr("dy", ".71em")
               .style("text-anchor", "end")
               .text(yLabel);

            svg.selectAll(".bar")
               .data(data) 
               .enter().append("rect")
               .attr("class", "bar")
               .attr("x", function(d) { return x(d.bin); })
               .attr("width", x.rangeBand())
               .attr("y", function(d) { return y(d.value); })
               .attr("height", function(d) { return chHeight - y(d.value); })
               .on("mouseover", function(d, i) {
                    div.transition()
                       .duration(200)
                       .style("opacity", .9);
                    div.html(d.value)
                       .style("left", (d3.event.pageX) + "px")     
                       .style("top", (d3.event.pageY - 50) + "px");
                })
               .on("mouseout", function(d, i) {
                    div.transition()
                       .duration(500)
                       .style("opacity", 0);
                });
          }).header("Content-Type","application/x-www-form-urlencoded")
            .send("POST", postData);
}