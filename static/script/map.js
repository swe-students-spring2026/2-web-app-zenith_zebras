const NYU_CNETER = [40.73077810827138, -73.99732127116461];
// const studySpots = [
//   {
//     _id: "1",
//     location: "Bobst",
//     googlemaps:
//       "https://www.google.com/maps/place/Elmer+Holmes+Bobst+Library/@40.7294279,-73.9972212,17z/data=!3m1!4b1!4m6!3m5!1s0x89c2599051b30887:0x6028dd2df0a0e9a2!8m2!3d40.7294279!4d-73.9972212!16s%2Fm%2F025rt0t?entry=ttu&g_ep=EgoyMDI2MDIxOC4wIKXMDSoASAFQAw%3D%3D",
//   },
//   {
//     _id: "2",
//     location: "Paulson",
//     googlemaps:
//       "https://www.google.com/maps/place/John+A.+Paulson+Center/@40.7266231,-73.9975583,17z/data=!4m14!1m7!3m6!1s0x89c2598f1c7ed16f:0x60eb5f760963ed17!2sJohn+A.+Paulson+Center!8m2!3d40.7266231!4d-73.9975583!16s%2Fg%2F11k3_p859g!3m5!1s0x89c2598f1c7ed16f:0x60eb5f760963ed17!8m2!3d40.7266231!4d-73.9975583!16s%2Fg%2F11k3_p859g?entry=ttu&g_ep=EgoyMDI2MDIxOC4wIKXMDSoASAFQAw%3D%3D",
//   },
//   {
//     _id: "3",
//     location: "Think Coffee",
//     googlemaps:
//       "https://www.google.com/maps/place/Think+Coffee/@40.728338,-73.995286,16.25z/data=!4m10!1m2!2m1!1sThink+Coffee!3m6!1s0x89c259851852abd5:0xd439f8da9b71229b!8m2!3d40.728338!4d-73.995286!15sCgxUaGluayBDb2ZmZWUiA4gBAVoOIgx0aGluayBjb2ZmZWWSAQtjb2ZmZWVfc2hvcOABAA!16s%2Fg%2F1td1fb3d?entry=ttu&g_ep=EgoyMDI2MDIxOC4wIKXMDSoASAFQAw%3D%3D",
//   },
// ];

// function extractLatLng(url) {
//   const match = url.match(/@(-?\d+\.?\d*),(-?\d+\.?\d*)/);
//   if (match) {
//     return { lat: parseFloat(match[1]), lng: parseFloat(match[2]) };
//   }
//   return null;
// }

const map = L.map("map", {
  zoomControl: true,
}).setView(NYU_CNETER, 18);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

function addMarkers(spots) {
  console.log(spots);
  spots.forEach((spot) => {
    // const coords = extractLatLng(spot.googlemaps);
    const coords = spot["latlng"];
    if (coords) {
      const marker = L.marker([coords.lat, coords.lng], {
        title: spot.location,
      }).addTo(map);

      // TODO
      // after implementing the page, add a link to the popup to redirect to the spot page for more info
      marker.bindPopup(
        `<a href='/posts/${spot._id}'><b>${spot.location}</b></a>`,
      );
    }
  });
}

addMarkers(posts);

/* ---------- circle section ---------- */
// const MILES_TO_METER = 1609;

// function milesToMeters(mi) {
//   return mi * MILES_TO_METER;
// }

// let centerMarker = null;
// let radiusCircle = null;

// const radiusInput = document.getElementById("radius");
// const radiusValue = document.getElementById("radiusValue");

// function getRadiusMiles() {
//   return Number(radiusInput.value);
// }

// function updateRadiusLabel() {
//   radiusValue.textContent = getRadiusMiles();
// }

// updateRadiusLabel();

/* ---------- for debugging ----------- */
// TODO comment these when pushing and submitting
// function onMapClick(e) {
//   const latlng = e.latlng;
//   console.log(`[${latlng.lat}, ${latlng.lng}]`);
// }

// map.on("click", onMapClick);
/* ---------- for debugging ----------- */
