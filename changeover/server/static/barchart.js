
function barChart(data, parentID, width, height, title, xLabel, yLabel) {
    var margin = {top: 40, right: 40, bottom: 30, left: 60},
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

    $(parentID).empty();
    var svg = d3.select(parentID).append("svg")
                .attr("width", chWidth + margin.left + margin.right)
                .attr("height", chHeight + margin.top + margin.bottom)
                .append("g")
                .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    x.domain(data.map(function(d) { return d.bin; }));
    y.domain([0, d3.max(data, function(d) { return d.value; })]);

    svg.append("text")
       .attr("x", (chWidth / 2))
       .attr("y", 0 - (margin.top / 2))
       .attr("text-anchor", "middle")
       .style("font-weight", "bold")
       .style("font-family", "'Quicksand', Arial, sans-serif")
       .style("font-size", "16px")
       .text(title);

    svg.append("g")
       .attr("class", "x axis")
       .attr("transform", "translate(0," + chHeight + ")")
       .call(xAxis)
       .append("text")
       .attr("class", "label")
       .attr("x", chWidth + 40)
       .attr("y", 19)
       .style("text-anchor", "end")
       .style("font-family", "'Droid Serif', Arial, sans-serif")
       .text(xLabel);

    svg.append("g")
       .attr("class", "y axis")
       .call(yAxis)
       .append("text")
       .attr("transform", "rotate(-90)")
       .attr("y", -50)
       .attr("dy", ".71em")
       .style("text-anchor", "end")
       .style("font-family", "'Droid Serif', Arial, sans-serif")
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
               .duration(300)
               .style("opacity", .9);
            div.html(d.value.toFixed(2))
               .style("left", (d3.event.pageX) + "px")     
               .style("top", (d3.event.pageY - 50) + "px");
        })
       .on("mouseout", function(d, i) {
            div.transition()
               .duration(500)
               .style("opacity", 0);
        });
}
