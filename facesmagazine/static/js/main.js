console.log('JavaScript OK');

const body = document.getElementById("page");
// const logo = document.getElementById("logo");

const homepage = document.querySelectorAll('.slider').length > 0 ? true : false;
// const archives = document.querySelectorAll('#archive').length > 0 ? true : false;

// const sectionA = document.getElementById("home");
const sectionA = document.querySelector(".section-a");

const homeIssueLink = document.querySelector("#link");
let homeIssueLinkBackUp;
if (homepage) {
    homeIssueLinkBackUp = homeIssueLink.getAttribute('href');
}
const slider1 = document.querySelector(".slider-1");
const slider2 = document.querySelector(".slider-2");
const slider3 = document.querySelector(".slider-3");

const sectionB = document.querySelector(".section-b");
const closeIcon = document.getElementById("close-icon");
const menuItems = document.querySelectorAll(".menu-item");
const pages = document.querySelectorAll(".page");


function toggleSectionB() {
    sectionB.classList.toggle("section-b-on");
    sectionB.classList.toggle("section-b-off");
    sectionA.classList.toggle("blurry");
}


function rollSlider() {
    setTimeout(function() {
        slider1.style.opacity = 0;
        slider2.style.opacity = 1;
    }, 3000);
    setTimeout(function() {
        slider2.style.opacity = 0;
        slider3.style.opacity = 1;
        if (homeIssueLink.getAttribute('shop') == "True") {
            if (homeIssueLink.getAttribute('user') != "None") {
                homeIssueLink.setAttribute('href', '/shop/');
            }
            else {
                homeIssueLink.setAttribute('href', '/accounts/inscription/');
            }
        }
    }, 6000);
    setTimeout(function() {
        slider3.style.opacity = 0;
        slider1.style.opacity = 1;
        homeIssueLink.setAttribute('href', homeIssueLinkBackUp);
    }, 9000);
}

function cloneFormAddress() {
    let addressForm1 = document.querySelectorAll('#account-form .account .address input');
    let addressForm2 = document.querySelectorAll('#account-form .account .delivery-address input');
    let region = document.getElementById("id_region");
    let delivery_region = document.getElementById("id_delivery_region");
    delivery_region.value = region.value;
    for (let i=0 ; i < addressForm1.length ; i++) {
        addressForm2[i+1].value = addressForm1[i].value;
    }
}

function emptyDeliveryAddress() {
    let delivery_region = document.getElementById("id_delivery_region");
    let formImputs = document.querySelectorAll('.delivery-address input');
    formImputs.forEach(input => {input.value = ""});
    delivery_region.value = 'FRANCE';
}


body.style.opacity = 0;
document.addEventListener("DOMContentLoaded", function(event) {
    console.log("DOM loaded");
    body.classList.add('visible');
    if (homepage) {
        rollSlider();
        setInterval(rollSlider, 12000);
    }
    setTimeout(function() {
        body.style.opacity = 1;
    }, 2000);
    // If we are not on 'prix Faces' page
    if (pages[3].classList.contains("hidden")) {
        pages[0].classList.remove("hidden")
    }
});




document.addEventListener("click", function(event) {
    if (
        (event.target.classList.contains('menu-call') || event.target.id == "close-icon")
        || (sectionA.contains(event.target) && sectionB.classList.contains('section-b-on'))
        ) {
        toggleSectionB();
    }
    // if (
    //     (event.target.classList.contains('contact-call') || event.target.id == "close-icon")
    //     || (sectionA.contains(event.target) && sectionC.classList.contains('section-c-on'))
    //     ) {
    //     toggleSectionC();
    // }
    else if (event.target.classList.contains('menu-item')) {
        menuItems.forEach(menuItem => { menuItem.classList.remove("active") });
        event.target.classList.add("active");
        pages.forEach(page => { page.classList.add("hidden") });
        document.getElementById(event.target.id + "-text").classList.toggle("hidden");
    }
    else if (event.target.classList.contains('issue-title')) {
        if (!event.target.classList.contains('active')) {
            document.querySelectorAll('.issue-titles .active').forEach(elt => {elt.classList.remove('active')});
            event.target.classList.add('active');
            if (event.target.classList.contains('a')) {
                document.querySelector(".issue-content.a").classList.remove('hidden');
                document.querySelector(".issue-content.b").classList.add('hidden');
            }
            else if (event.target.classList.contains('b')) {
                document.querySelector(".issue-content.a").classList.add('hidden');
                document.querySelector(".issue-content.b").classList.remove('hidden');
            }
        }
    }
    else if (event.target.id == "same-address") {
        /* TODO this function may not working in case of manual or auto-refresh */
        const address = document.querySelector(".address");
        const addressRegion = document.querySelector(".address select");
        const DeliveryAddress = document.querySelector(".delivery-address");
        const checkButton = document.getElementById("same-address");

        if (event.target.checked) {
            cloneFormAddress();
            address.addEventListener("keyup", function(event) {
                if (checkButton.checked) {
                    checkButton.checked = false;
                    emptyDeliveryAddress();
                }
            });
            addressRegion.addEventListener('input', function (event) {
                if (checkButton.checked) {
                    checkButton.checked = false;
                    emptyDeliveryAddress();
                }
            });
            DeliveryAddress.addEventListener("keyup", function(event) {
                checkButton.checked = false;
            });
        }
        else {
            emptyDeliveryAddress();
        }
    }
  });

